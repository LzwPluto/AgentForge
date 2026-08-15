from textual.widgets import Static
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from config import config
from core.memory import SharedMemory, AgentStatus


class AgentStatusCardsWidget(Static):
    """5 大 Agent 槽位状态看板组件（支持轮次追踪、工具状态显示与美化排版）"""

    DEFAULT_CSS = """
    AgentStatusCardsWidget {
        width: 100%;
        height: auto;
        border: solid #6366f1;
        background: #111827;
        padding: 0 1;
    }
    """

    def __init__(self, memory: SharedMemory, **kwargs):
        super().__init__(**kwargs)
        self.memory = memory

    def on_mount(self) -> None:
        self.refresh_cards()

    def refresh_cards(self) -> None:
        """重新渲染 5 个槽位状态"""
        table = Table(
            show_header=False,
            expand=True,
            box=None,
            padding=(0, 1),
        )
        # 固定 5 列均匀分布
        for _ in range(5):
            table.add_column(ratio=1)

        card_cells = []
        for i in range(1, 6):
            slot_id = f"slot_{i}"
            slot_cfg = config.get_slot(slot_id)
            st = self.memory.agent_states.get(slot_id, {})

            is_enabled = slot_cfg.enabled if slot_cfg else False
            status = st.get("status", AgentStatus.DISABLED if not is_enabled else AgentStatus.IDLE)
            action = st.get("last_action", "未启用" if not is_enabled else "空闲待命中")

            if is_enabled and slot_cfg:
                icon = slot_cfg.icon or "🤖"
                name = slot_cfg.name
                model_name = slot_cfg.model or "default"
                allow_tools = slot_cfg.allow_tools
                tool_tag = "[green]🛠️开[/green]" if allow_tools else "[dim]💬纯对话[/dim]"
                badge = self._get_status_badge(status)

                # 智能格式化显示名称，防止中途截断导致漏右括号 ')'
                disp_name = name
                if len(disp_name) > 18:
                    if "(" in disp_name:
                        main_part, _, paren_part = disp_name.partition("(")
                        disp_name = f"{main_part.strip()[:10]} ({paren_part[:4]}...)"
                    else:
                        disp_name = disp_name[:17] + "…"

                disp_model = model_name if len(model_name) <= 12 else model_name[:10] + "…"

                cell_text = (
                    f"[bold #38bdf8]{icon} {disp_name}[/bold #38bdf8]\n"
                    f"[dim #94a3b8]{disp_model} | {tool_tag}[/dim #94a3b8]\n"
                    f"{badge}\n"
                    f"[dim]{action[:18]}[/dim]"
                )
            else:
                cell_text = (
                    f"[dim white]⚪ 槽位 {i} (未启用)[/dim white]\n"
                    f"[dim #475569]───── 空闲 ─────[/dim #475569]\n"
                    f"[dim #64748b]⚪ 成员未指派[/dim #64748b]\n"
                    f"[dim #475569]按 F1 设置启用[/dim #475569]"
                )

            card_cells.append(cell_text)

        table.add_row(*card_cells)

        enabled_count = len(config.get_enabled_slots())
        cur_round = self.memory.current_round
        max_r = self.memory.max_rounds
        round_tag = f" · [bold yellow]第 {cur_round}/{max_r} 轮接力[/bold yellow]" if cur_round > 0 else ""

        panel = Panel(
            table,
            title=f"[bold #818cf8]🤖 多 Agent 协同编队 (当前启用 {enabled_count}/5 位成员{round_tag})[/bold #818cf8]",
            border_style="#6366f1",
            padding=(0, 0),
        )
        self.update(panel)

    @staticmethod
    def _get_status_badge(status: AgentStatus) -> str:
        if status == AgentStatus.IDLE:
            return "[green]🟢 倾听/待命中[/green]"
        elif status == AgentStatus.SPEAKING:
            return "[bold bright_green]▶️ 轮流发言中[/bold bright_green]"
        elif status == AgentStatus.THINKING:
            return "[yellow]🟡 深度思考中...[/yellow]"
        elif status == AgentStatus.EXECUTING_TOOL:
            return "[blue]🔵 调用沙箱工具...[/blue]"
        elif status == AgentStatus.PAUSED:
            return "[bold yellow]⏸ 暂停等待[/bold yellow]"
        elif status == AgentStatus.ERROR:
            return "[red]🔴 发生异常[/red]"
        elif status == AgentStatus.FINISHED:
            return "[bright_green]✨ 阶段完成[/bright_green]"
        elif status == AgentStatus.DISABLED:
            return "[dim white]⚪ 未启用[/dim white]"
        return f"[white]{status}[/white]"
