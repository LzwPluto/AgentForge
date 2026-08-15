from textual.widgets import Static
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from core.memory import SharedMemory, TaskItem, TaskStatus


class TaskBoardWidget(Static):
    """任务看板列表组件"""

    DEFAULT_CSS = """
    TaskBoardWidget {
        width: 100%;
        height: 100%;
        border: solid #3b82f6;
        background: #111827;
        padding: 0 1;
    }
    """

    def __init__(self, memory: SharedMemory, **kwargs):
        super().__init__(**kwargs)
        self.memory = memory

    def on_mount(self) -> None:
        self.refresh_tasks()

    def refresh_tasks(self) -> None:
        """根据 SharedMemory 中的任务重新渲染表格"""
        table = Table(
            show_header=True,
            header_style="bold cyan",
            expand=True,
            box=None,
            padding=(0, 1),
        )
        table.add_column("状态", width=8)
        table.add_column("负责成员", width=12)
        table.add_column("任务标题", style="bold")

        if not self.memory.tasks:
            table.add_row("○ 待命", "-", "[dim]等待输入目标由主持人拆解指派...[/dim]")
        else:
            for t in self.memory.tasks:
                status_text = self._format_status(t.status)
                assignee_text = f"[cyan]{t.assigned_name[:10]}[/cyan]"
                table.add_row(status_text, assignee_text, t.title)

        panel = Panel(
            table,
            title="[bold cyan]📋 协同任务看板 (Task Board)[/bold cyan]",
            border_style="blue",
            padding=(0, 0),
        )
        self.update(panel)

    @staticmethod
    def _format_status(status: TaskStatus) -> Text:
        if status == TaskStatus.PENDING:
            return Text("○ 待办", style="dim white")
        elif status == TaskStatus.IN_PROGRESS:
            return Text("▶ 进行中", style="bold yellow")
        elif status == TaskStatus.COMPLETED:
            return Text("✔ 完成", style="bold green")
        elif status == TaskStatus.FAILED:
            return Text("✖ 失败", style="bold red")
        elif status == TaskStatus.BLOCKED:
            return Text("⏸ 中止", style="bold magenta")
        return Text(str(status), style="white")
