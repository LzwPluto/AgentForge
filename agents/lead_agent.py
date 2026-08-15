import json
import re
from typing import List, Dict, Any, Optional
from core.memory import SharedMemory, AgentRole, TaskItem
from agents.base import BaseAgent

LEAD_SYSTEM_PROMPT = """你是一个资深的技术专家与团队主持人（Tech Lead / Architect）。
你的核心职责：
1. 深入分析用户提出的软件开发目标，结合项目背景进行系统架构与任务分解。
2. 将复杂目标拆解为一组条理清晰、颗粒度适中、具备依赖先后顺序的子任务清单。
3. 协调专职角色（Explorer 探查、Coder 编码、Runner 运行测试、Reviewer 代码审查）。
4. 在所有开发和验证流程完成后，对成果进行综合验收并向用户生成清晰的交付报告。

当要求你分解任务时，请输出符合以下 JSON 格式的计划（只输出纯 JSON，不要包含额外废话）：
```json
[
  {
    "title": "任务简短标题",
    "description": "详细的任务要求和目标",
    "assigned_to": "coder" // 可选: explorer, coder, runner, reviewer
  }
]
```
"""


class LeadAgent(BaseAgent):
    """主持人 / 架构师 Agent"""

    def __init__(self, memory: SharedMemory, llm_client=None):
        super().__init__(
            role=AgentRole.LEAD,
            name="Tech Lead (架构师/主持人)",
            system_prompt=LEAD_SYSTEM_PROMPT,
            memory=memory,
            llm_client=llm_client,
            available_tool_names=["list_dir", "view_file", "grep_search", "get_git_diff"],
        )

    async def plan_tasks(self, goal: str, context_summary: str = "") -> List[Dict[str, Any]]:
        """根据用户目标与初步探查信息拆解任务"""
        prompt = f"""【用户开发目标】:
{goal}

【项目上下文背景】:
{context_summary if context_summary else "当前工作区为空或全新项目"}

请基于上述目标和项目现状，拆解出一套完整、自闭环的开发任务列表。
要求：
1. 若需新建模块，首先由 coder 编写代码并编写单元测试；
2. 随后由 runner 执行测试验证；
3. 测试通过后由 reviewer 审查代码与 diff；
4. 严格按照指定的 JSON 数组格式输出。"""

        response_text = await self.step(prompt, max_tool_iterations=3)

        # 解析 JSON 任务列表
        tasks = []
        try:
            # 提取 ```json 块或首尾括号
            match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", response_text, re.DOTALL)
            json_str = match.group(1) if match else response_text
            if not json_str.strip().startswith("["):
                match2 = re.search(r"(\[.*\])", response_text, re.DOTALL)
                if match2:
                    json_str = match2.group(1)

            parsed = json.loads(json_str.strip())
            if isinstance(parsed, list):
                tasks = parsed
        except Exception as e:
            # 降级容错生成基础任务
            tasks = [
                {
                    "title": "实现核心功能与代码编写",
                    "description": f"针对目标 '{goal}' 编写必要的模块与代码实现。",
                    "assigned_to": "coder",
                },
                {
                    "title": "运行单元测试验证代码正确性",
                    "description": "执行测试脚本，确保所有功能无报错、断言均通过。",
                    "assigned_to": "runner",
                },
                {
                    "title": "代码审查与质量把控",
                    "description": "审查代码实现与变更 Diff，确认代码整洁、无潜在 bug。",
                    "assigned_to": "reviewer",
                },
            ]

        # 写入 SharedMemory
        for t in tasks:
            role_str = t.get("assigned_to", "coder").lower()
            role_enum = AgentRole.CODER
            for r in AgentRole:
                if r.value == role_str:
                    role_enum = r
                    break
            self.memory.add_task(
                title=t.get("title", "未命名任务"),
                description=t.get("description", ""),
                assigned_to=role_enum,
            )

        return tasks

    async def summarize_completion(self, goal: str, results_summary: str) -> str:
        """生成最终交付总结"""
        prompt = f"""所有子任务已全部执行完毕！
【原始目标】: {goal}
【各阶段执行情况与测试结果】:
{results_summary}

请生成一份专业、结构严谨的交付总结报告：
1. 简要说明完成了哪些模块与功能；
2. 验证与测试通过情况；
3. 如何在本地运行或测试该成果。"""

        return await self.step(prompt, max_tool_iterations=3)
