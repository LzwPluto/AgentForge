from typing import Tuple
from core.memory import SharedMemory, AgentRole, TaskItem
from agents.base import BaseAgent

REVIEWER_SYSTEM_PROMPT = """你是一个严谨的代码审查与质检架构师（Reviewer Agent）。
你的核心职责：
1. 使用 `get_git_diff` 工具获取所有修改与新增代码的 Diff 补丁，并可结合 `view_file` 查看完整源文件。
2. 审查代码质量：
   - 逻辑正确性与边界情况处理（如空值、越界、并发安全等）；
   - 代码风格、类型提示、命名规范与注释；
   - 是否包含安全隐患（如硬编码密钥、SQL注入、不安全的系统调用等）。
3. 如果代码合格且无重大隐患，请在回复中明确写出 “【审查通过】”；
4. 如果发现代码缺陷或需要改进，请在回复中明确写出 “【审查发现问题】” 并列出具体修改建议。
"""


class ReviewerAgent(BaseAgent):
    """代码质量与安全审查专家 Agent"""

    def __init__(self, memory: SharedMemory, llm_client=None):
        super().__init__(
            role=AgentRole.REVIEWER,
            name="Reviewer (代码审查专家)",
            system_prompt=REVIEWER_SYSTEM_PROMPT,
            memory=memory,
            llm_client=llm_client,
            available_tool_names=["get_git_diff", "view_file"],
        )

    async def review_changes(self, task: TaskItem) -> Tuple[bool, str]:
        """审查代码变更与质量"""
        prompt = f"""【代码审查目标】:
针对任务: {task.title}
任务描述: {task.description}

请使用 `get_git_diff` 查看当前的代码修改补丁，并视需要使用 `view_file` 检查源文件。
给出你的审查结论：
- 若符合标准且无重大缺陷，请包含 “【审查通过】”；
- 若存在明显 bug 或隐患，请包含 “【审查发现问题】” 并详细指出代码位置和修复建议。"""

        response_text = await self.step(prompt, max_tool_iterations=5)
        is_approved = "【审查通过】" in response_text or ("通过" in response_text and "未通过" not in response_text and "【审查发现问题】" not in response_text)
        if "【审查发现问题】" in response_text or "未通过" in response_text:
            is_approved = False

        return is_approved, response_text
