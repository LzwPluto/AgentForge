from core.memory import SharedMemory, AgentRole, TaskItem
from agents.base import BaseAgent

CODER_SYSTEM_PROMPT = """你是一个顶级全栈软件工程师（Coder Agent）。
你的核心职责：
1. 负责编写高质量、健壮、模块化、带完备类型注解与注释的生产级代码。
2. 创建新文件时使用 `write_file`。
3. 修改现有文件时：
   - 必须先使用 `view_file` 确认准确行号与上下文内容；
   - 使用 `edit_file_exact` 进行精准替换，确保 `target_content` 与原文件完全一致（包括空格和缩进），严禁破坏无关代码。
4. 严格按照最佳工程实践编写配套的单元测试（如 pytest）。
5. 如果收到 Runner 的报错反馈，仔细分析 Traceback，定位根本原因并精确修复。
"""


class CoderAgent(BaseAgent):
    """编码实现与修复专家 Agent"""

    def __init__(self, memory: SharedMemory, llm_client=None):
        super().__init__(
            role=AgentRole.CODER,
            name="Coder (编码专家)",
            system_prompt=CODER_SYSTEM_PROMPT,
            memory=memory,
            llm_client=llm_client,
            available_tool_names=["view_file", "write_file", "edit_file_exact", "grep_search", "list_dir"],
        )

    async def execute_task(self, task: TaskItem, feedback_or_error: str = "") -> str:
        """执行具体编码任务或修复报错"""
        context_msg = f"""【当前指派任务】:
任务标题: {task.title}
任务描述: {task.description}
"""
        if feedback_or_error:
            context_msg += f"""
⚠️ 【上一轮测试/审查反馈的错误信息】:
{feedback_or_error}
请仔细阅读上述报错日志与堆栈，找出 bug 根源并对代码进行精确修复！
"""
        else:
            context_msg += "\n请开始编写或修改相关代码，并在完成后给出简明的工作摘要。"

        return await self.step(context_msg, max_tool_iterations=12)
