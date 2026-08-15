import json
import logging
from typing import List, Dict, Any, Optional, Callable
from pydantic import BaseModel

from config import config
from core.llm_client import LLMClient, LLMResponse, ToolCallRequest
from core.tools import ToolDispatcher, OPENAI_TOOL_DEFINITIONS
from core.memory import SharedMemory, AgentRole, AgentStatus, EventType

logger = logging.getLogger(__name__)


class BaseAgent:
    """Agent 基类，封装系统提示词、工具调用循环、消息历史与状态同步"""

    def __init__(
        self,
        role: AgentRole,
        name: str,
        system_prompt: str,
        memory: SharedMemory,
        llm_client: Optional[LLMClient] = None,
        available_tool_names: Optional[List[str]] = None,
    ):
        self.role = role
        self.name = name
        self.system_prompt = system_prompt
        self.memory = memory
        self.llm_client = llm_client or LLMClient()
        self.model = config.get_model_for_role(role.value)
        self.history: List[Dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt}
        ]

        # 过滤该 Agent 允许使用的工具
        self.available_tool_names = available_tool_names
        if available_tool_names is not None:
            self.tool_definitions = [
                t for t in OPENAI_TOOL_DEFINITIONS
                if t["function"]["name"] in available_tool_names
            ]
        else:
            self.tool_definitions = OPENAI_TOOL_DEFINITIONS

    def reset_history(self) -> None:
        """重置历史对话，保留 system prompt"""
        self.history = [{"role": "system", "content": self.system_prompt}]

    async def step(
        self,
        user_message: str,
        max_tool_iterations: int = 10,
        on_token: Optional[Callable[[str], None]] = None,
    ) -> str:
        """执行单轮或多轮工具调用直到产生最终结论"""
        self.history.append({"role": "user", "content": user_message})
        self.memory.update_agent_state(self.role, AgentStatus.THINKING, "开始思考...")

        iteration = 0
        final_answer = ""

        while iteration < max_tool_iterations:
            iteration += 1

            def _token_stream_wrapper(token: str):
                if on_token:
                    on_token(token)
                self.memory.publish(EventType.TOKEN_STREAM, {
                    "role": self.role,
                    "token": token,
                })

            response: LLMResponse = await self.llm_client.chat(
                messages=self.history,
                tools=self.tool_definitions if self.tool_definitions else None,
                model=self.model,
                on_token_stream=_token_stream_wrapper,
            )

            # 记录助理文本响应
            assistant_msg: Dict[str, Any] = {
                "role": "assistant",
                "content": response.content or "",
            }

            if response.tool_calls:
                # 记录带 tool_calls 的消息
                raw_tc_list = []
                for tc in response.tool_calls:
                    raw_tc_list.append({
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments, ensure_ascii=False)
                            if isinstance(tc.arguments, dict)
                            else tc.raw_arguments_str,
                        },
                    })
                assistant_msg["tool_calls"] = raw_tc_list
                self.history.append(assistant_msg)

                # 依次分发执行工具
                for tc in response.tool_calls:
                    self.memory.update_agent_state(
                        self.role,
                        AgentStatus.EXECUTING_TOOL,
                        f"执行工具: {tc.name}",
                    )
                    self.memory.log_message(
                        sender=self.role,
                        content=f"🛠️ [调用工具 {tc.name}]:\n参数: {json.dumps(tc.arguments, ensure_ascii=False, indent=2)}",
                        msg_type="tool_call",
                        metadata={"tool_name": tc.name, "args": tc.arguments},
                    )

                    tool_res = await ToolDispatcher.dispatch(tc.name, tc.arguments)
                    result_str = tool_res.to_string()

                    self.memory.log_message(
                        sender=self.role,
                        content=f"📋 [工具 {tc.name} 返回结果]:\n{result_str[:800]}" + ("..." if len(result_str) > 800 else ""),
                        msg_type="tool_result",
                        metadata={"success": tool_res.success},
                    )

                    # 若工具修改了文件，发布 Diff 更新事件
                    if tc.name in ("write_file", "edit_file_exact"):
                        self.memory.publish(EventType.DIFF_UPDATED, {
                            "file": tc.arguments.get("path"),
                            "tool": tc.name,
                        })

                    # 将工具执行结果作为 tool role 追加到对话历史
                    self.history.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result_str,
                    })

                # 工具执行完毕，继续下一轮循环让模型处理结果
                self.memory.update_agent_state(self.role, AgentStatus.THINKING, "分析工具执行结果...")
                continue
            else:
                # 没有工具调用，输出最终结论
                self.history.append(assistant_msg)
                final_answer = response.content or ""
                self.memory.log_message(
                    sender=self.role,
                    content=final_answer,
                    msg_type="thought",
                )
                break

        self.memory.update_agent_state(self.role, AgentStatus.IDLE, "任务阶段完成")
        return final_answer
