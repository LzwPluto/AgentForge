import re
from typing import Dict, Any, Tuple
from core.memory import SharedMemory, AgentRole, TaskItem
from agents.base import BaseAgent

RUNNER_SYSTEM_PROMPT = """你是一个专业的测试与环境执行专家（Runner Agent）。
你的核心职责：
1. 负责在本地终端中运行构建脚本、单元测试套件（如 `pytest`、`python -m unittest`、`node test` 等）以及语法检查。
2. 使用 `run_command` 工具执行命令并监控输出与退出码。
3. 如果测试全部通过（Exit code: 0 且所有断言通过），确认成果并输出“【测试通过】”。
4. 如果测试报错或失败，提取核心 Traceback 堆栈信息，精准提炼失败原因，并输出“【测试失败】”，明确指引 Coder 修复。
"""


class RunnerAgent(BaseAgent):
    """测试与命令执行专家 Agent"""

    def __init__(self, memory: SharedMemory, llm_client=None):
        super().__init__(
            role=AgentRole.RUNNER,
            name="Runner (运行/测试专家)",
            system_prompt=RUNNER_SYSTEM_PROMPT,
            memory=memory,
            llm_client=llm_client,
            available_tool_names=["run_command", "view_file", "list_dir"],
        )

    async def run_and_verify(self, task: TaskItem, default_test_cmd: str = "pytest -v") -> Tuple[bool, str]:
        """运行测试并判断是否通过"""
        prompt = f"""【验证任务】:
任务标题: {task.title}
任务要求: {task.description}

请使用 `run_command` 工具执行相应的测试或验证命令（例如 `{default_test_cmd}` 或适合该项目的测试命令）。
执行后请分析测试结果：
- 若所有测试通过，请明确在回复中包含 “【测试通过】”；
- 若测试失败或报错，请明确在回复中包含 “【测试失败】” 并详细附上失败的函数、行号和 Traceback。"""

        response_text = await self.step(prompt, max_tool_iterations=6)

        is_passed = "【测试通过】" in response_text or "passed" in response_text.lower() and "failed" not in response_text.lower() and "error" not in response_text.lower()
        if "【测试失败】" in response_text:
            is_passed = False

        return is_passed, response_text
