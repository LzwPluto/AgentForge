from core.memory import SharedMemory, AgentRole
from agents.base import BaseAgent

EXPLORER_SYSTEM_PROMPT = """你是一个敏锐的代码探查与逆向分析专家（Explorer Agent）。
你的核心职责：
1. 快速探查目标代码仓库的目录结构、核心技术栈与配置文件。
2. 使用 `list_dir` 查看目录层次，使用 `grep_search` 全文检索关键类、函数、变量或路由。
3. 使用 `view_file` 仔细阅读关键文件，找出与开发任务强相关的代码逻辑与上下游依赖。
4. 输出清晰精炼的项目现状分析报告，为后续 Coder 的编写提供精准的上下文指导。
"""


class ExplorerAgent(BaseAgent):
    """代码库探查专家 Agent"""

    def __init__(self, memory: SharedMemory, llm_client=None):
        super().__init__(
            role=AgentRole.EXPLORER,
            name="Explorer (探查专家)",
            system_prompt=EXPLORER_SYSTEM_PROMPT,
            memory=memory,
            llm_client=llm_client,
            available_tool_names=["list_dir", "grep_search", "view_file"],
        )

    async def explore_workspace(self, goal: str) -> str:
        """探查工作区现状并汇报"""
        prompt = f"""请探查当前工作区环境与代码现状，以协助完成开发目标：
【目标】: {goal}

请使用你的探查工具（如 list_dir、grep_search、view_file）：
1. 检查当前目录下已有哪些文件与结构；
2. 查找是否有与目标相关的现有代码、依赖或配置文件；
3. 输出精炼的探查总结，指出现有架构与需要新建/修改的关键位置。"""

        return await self.step(prompt, max_tool_iterations=6)
