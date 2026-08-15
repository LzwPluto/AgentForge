from textual.widgets import Static
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text

from core.tools import SandboxTools


class DiffViewerWidget(Static):
    """代码变动实时 Diff 视图组件"""

    DEFAULT_CSS = """
    DiffViewerWidget {
        width: 100%;
        height: 100%;
        border: solid #f59e0b;
        background: #111827;
        padding: 0 1;
    }
    """

    def on_mount(self) -> None:
        self.refresh_diff()

    def refresh_diff(self, specific_path: str = "") -> None:
        """刷新 Diff 显示"""
        res = SandboxTools.get_git_diff(path=specific_path if specific_path else None)
        diff_text = res.output if res.success else f"无法读取 Diff: {res.error}"

        if not diff_text or "clean" in diff_text.lower() or diff_text.strip() == "":
            panel = Panel(
                Text("暂无代码变动或当前工作区未初始化 Git 仓库。", style="dim white"),
                title="[bold yellow]📝 代码变更预览 (Diff Preview)[/bold yellow]",
                border_style="yellow",
            )
        else:
            syntax = Syntax(
                diff_text,
                lexer="diff",
                theme="monokai",
                line_numbers=False,
                word_wrap=True,
            )
            panel = Panel(
                syntax,
                title="[bold yellow]📝 代码变更预览 (Diff Preview)[/bold yellow]",
                border_style="yellow",
            )

        self.update(panel)
