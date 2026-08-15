import json
import logging
import asyncio
from typing import List, Dict, Any, Optional, Callable

from config import config, AgentSlotConfig
from core.llm_client import LLMClient, LLMResponse, ToolCallRequest
from core.tools import ToolDispatcher, OPENAI_TOOL_DEFINITIONS
from core.memory import SharedMemory, AgentStatus, EventType

logger = logging.getLogger(__name__)


class DynamicAgent:
    """可根据槽位配置动态实例化的全知圆桌 Agent (支持全工具与全局群聊上下文)"""

    def __init__(
        self,
        slot_config: AgentSlotConfig,
        memory: SharedMemory,
        llm_client: Optional[LLMClient] = None,
    ):
        self.slot_config = slot_config
        self.slot_id = slot_config.slot_id
        self.name = slot_config.name
        self.icon = slot_config.icon
        self.system_prompt = slot_config.system_prompt
        self.provider_id = slot_config.provider_id
        self.model = slot_config.model
        self.memory = memory
        self.llm_client = llm_client or LLMClient()

    @property
    def tool_definitions(self) -> List[Dict[str, Any]]:
        """获取当前角色被允许调用的工具 Schema 列表"""
        if not getattr(self.slot_config, "allow_tools", True):
            return []
        allowed = set(self.slot_config.allowed_tools)
        return [
            tool for tool in OPENAI_TOOL_DEFINITIONS
            if tool["function"]["name"] in allowed
        ]

    async def step_in_group(
        self,
        max_tool_iterations: int = 8,
        on_token: Optional[Callable[[str], None]] = None,
    ) -> str:
        """在全知群聊圆桌中执行当前轮次发言与工具调用"""
        self.memory.update_agent_state(self.slot_id, AgentStatus.SPEAKING, "正在思考并组织发言...")

        chat_context = self.memory.get_shared_llm_messages_for_agent(
            current_slot_id=self.slot_id,
            system_prompt=self.system_prompt,
        )

        iteration = 0
        final_answer = ""
        tool_calls_executed = []
        tool_results_recorded = []

        while iteration < max_tool_iterations:
            iteration += 1

            def _token_stream_wrapper(token: str, is_thinking: bool = False):
                if getattr(self.memory, "is_cancelled", False):
                    raise asyncio.CancelledError("协同任务已被终止")
                if on_token:
                    on_token(token)
                self.memory.publish(EventType.TOKEN_STREAM, {
                    "slot_id": self.slot_id,
                    "sender_name": self.name,
                    "sender_icon": self.icon,
                    "token": token,
                    "is_thinking": is_thinking,
                })

            try:
                response: LLMResponse = await self.llm_client.chat(
                    messages=chat_context,
                    tools=self.tool_definitions if self.tool_definitions else None,
                    provider_id=self.provider_id,
                    model=self.model,
                    thinking_mode=getattr(self.slot_config, "thinking_mode", "deep"),
                    on_token_stream=_token_stream_wrapper,
                )
            except asyncio.CancelledError:
                self.memory.update_agent_state(self.slot_id, AgentStatus.IDLE, "任务已终止待命")
                return ""

            except Exception as e:
                prov = config.get_provider(self.provider_id)
                prov_name = prov.name if prov else self.provider_id
                prov_url = prov.base_url if prov else ""
                err_msg = (
                    f"❌ **【大模型 API 调用失败】**\n"
                    f"• 角色: {self.icon} {self.name} (槽位: {self.slot_id})\n"
                    f"• 绑定的供应商: {prov_name} ({prov_url})\n"
                    f"• 绑定的模型: `{self.model}`\n"
                    f"• 错误信息: {str(e)}\n\n"
                    f"👉 请按 F1 检查该角色的【绑定的 API 供应商】与【模型名称】配置是否正确。"
                )
                self.memory.log_message(
                    sender_id=self.slot_id,
                    sender_name=self.name,
                    sender_icon=self.icon,
                    content=err_msg,
                    msg_type="error",
                )
                self.memory.update_agent_state(self.slot_id, AgentStatus.ERROR, "API调用失败")
                return err_msg

            assistant_msg: Dict[str, Any] = {
                "role": "assistant",
                "content": response.content or "",
            }


            if response.tool_calls:
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
                chat_context.append(assistant_msg)

                # 工具中文名称对照
                tool_names_map = {
                    "write_file": "写入文件",
                    "edit_file_exact": "编辑文件",
                    "view_file": "查看文件",
                    "list_dir": "浏览目录",
                    "grep_search": "全局搜索",
                    "run_command": "运行命令",
                    "get_git_diff": "查看代码变更",
                }

                # 分发执行工具
                for tc in response.tool_calls:
                    display_tool_name = tool_names_map.get(tc.name, tc.name)
                    self.memory.update_agent_state(
                        self.slot_id,
                        AgentStatus.EXECUTING_TOOL,
                        f"调用工具: {display_tool_name}",
                    )
                    self.memory.log_message(
                        sender_id=self.slot_id,
                        sender_name=self.name,
                        sender_icon=self.icon,
                        content=f"🛠️ 正在调用工具: [bold cyan]{display_tool_name} ({tc.name})[/bold cyan] [blink bold yellow]⚙️ 正在执行中...[/blink bold yellow]",
                        msg_type="tool_call",
                        metadata={"tool_name": tc.name, "args": tc.arguments},
                    )

                    tool_res = await ToolDispatcher.dispatch(tc.name, tc.arguments)
                    result_str = tool_res.to_string()
                    
                    tool_calls_executed.append({
                        "id": tc.id,
                        "name": tc.name,
                        "arguments": tc.arguments,
                    })
                    tool_results_recorded.append({
                        "tool": tc.name,
                        "output": result_str,
                        "success": tool_res.success,
                    })

                    status_icon = "✔" if tool_res.success else "✖"
                    status_color = "green" if tool_res.success else "red"
                    status_desc = "执行完毕" if tool_res.success else "执行异常"
                    self.memory.log_message(
                        sender_id=self.slot_id,
                        sender_name=self.name,
                        sender_icon=self.icon,
                        content=f"[{status_color}]{status_icon} 工具 {display_tool_name} ({tc.name}) {status_desc}[/{status_color}]",
                        msg_type="tool_result",
                        metadata={"success": tool_res.success},
                    )


                    if tc.name in ("write_file", "edit_file_exact"):
                        self.memory.publish(EventType.DIFF_UPDATED, {
                            "file": tc.arguments.get("path"),
                            "tool": tc.name,
                        })

                    chat_context.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result_str,
                    })

                self.memory.update_agent_state(self.slot_id, AgentStatus.SPEAKING, "分析工具结果并准备总结发言...")
                continue
            else:
                chat_context.append(assistant_msg)
                final_answer = response.content or ""
                self.memory.log_message(
                    sender_id=self.slot_id,
                    sender_name=self.name,
                    sender_icon=self.icon,
                    content=final_answer,
                    thinking_content=response.thinking_content or "",
                    msg_type="thought",
                    tool_calls=tool_calls_executed,
                    tool_results=tool_results_recorded,
                )
                break

        self.memory.update_agent_state(self.slot_id, AgentStatus.IDLE, "发言完毕，等待下一轮")
        return final_answer
