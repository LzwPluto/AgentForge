from textual.screen import ModalScreen
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal, ScrollableContainer
from textual.widgets import (
    Label, Button, Static, OptionList, Markdown
)
from textual.widgets.option_list import Option
from textual.binding import Binding

from core.history_manager import HistoryManager, HISTORY_DIR


class HistoryModal(ModalScreen[bool]):
    """多 Agent 历史协同会话管理弹窗（固定操作栏 + 支持鼠标滚轮全景预览）"""

    BINDINGS = [
        Binding("escape", "dismiss_modal", "返回/关闭 (ESC)", show=True),
        Binding("delete", "delete_current", "删除选中会话 (Del)", show=True),
    ]

    DEFAULT_CSS = """
    HistoryModal {
        align: center middle;
    }

    #history-dialog {
        padding: 0 1;
        width: 96;
        height: 94%;
        max-height: 42;
        border: thick #10b981;
        background: #0f172a;
    }

    #hist-header {
        dock: top;
        height: 3;
        background: #1e293b;
        padding: 0 1;
        align: left middle;
    }

    #hist-title {
        width: 1fr;
        color: #34d399;
        text-style: bold;
    }

    #hist-main {
        height: 1fr;
        margin: 1 0;
    }

    #hist-list-container {
        width: 35%;
        height: 100%;
        border-right: solid #334155;
        padding-right: 1;
    }

    #session_list {
        height: 1fr;
        background: #1e293b;
    }

    #hist-detail-container {
        width: 65%;
        height: 100%;
        padding-left: 1;
        background: #0b0f19;
    }

    #detail-scroll {
        height: 1fr;
        background: #0b0f19;
        overflow-y: scroll;
        padding: 0 1;
    }

    #hist-footer {
        dock: bottom;
        height: 3;
        background: #1e293b;
        padding: 0 1;
        align: right middle;
    }

    #hist-path-info {
        width: 1fr;
    }

    Button {
        margin-left: 1;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.sessions = []
        self.selected_session_id = ""

    def compose(self) -> ComposeResult:
        with Vertical(id="history-dialog"):
            with Horizontal(id="hist-header"):
                yield Static("📜 [bold #34d399]历史协同会话管理 (持久化归档与纪要导出)[/bold #34d399]", id="hist-title")
                yield Button("◀ 返回 (ESC)", variant="default", id="btn_back")

            with Horizontal(id="hist-main"):
                with Vertical(id="hist-list-container"):
                    yield Label("历史会话列表 (点击切换):", classes="form-label")
                    yield OptionList(id="session_list")

                with Vertical(id="hist-detail-container"):
                    yield Label("会话纪要详情 (滚轮可直接滚动):", classes="form-label")
                    with ScrollableContainer(id="detail-scroll"):
                        yield Markdown("选择左侧会话查看详细纪要", id="detail-markdown")

            with Horizontal(id="hist-footer"):
                yield Static(f"[dim]📁 归档目录: {HISTORY_DIR}[/dim]", id="hist-path-info")
                yield Button("🗑️ 删除此会话", variant="warning", id="btn_delete_one")
                yield Button("🧹 清空全部历史", variant="error", id="btn_clear_all")
                yield Button("◀ 返回主界面", variant="default", id="btn_close")

    def on_mount(self) -> None:
        self._refresh_list()

    def _refresh_list(self) -> None:
        """刷新会话列表"""
        self.sessions = HistoryManager.list_sessions()
        opt_list = self.query_one("#session_list", OptionList)
        opt_list.clear_options()

        if not self.sessions:
            opt_list.add_option(Option("暂无历史归档记录", id="none", disabled=True))
            self.query_one("#detail-markdown", Markdown).update("### 暂无历史归档记录\n每次多 Agent 协同执行完毕后，系统将自动归档全景记录于此。")
            self.selected_session_id = ""
            return

        for s in self.sessions:
            sid = s.get("session_id", "")
            date_str = s.get("date_str", sid)
            goal = s.get("goal", "")[:24]
            rounds = s.get("total_rounds", 1)
            opt_text = f"📅 {date_str}\n  🎯 {goal} ({rounds}轮)"
            opt_list.add_option(Option(opt_text, id=sid))

        self.selected_session_id = self.sessions[0].get("session_id", "")
        self._show_detail(self.selected_session_id)

    def _show_detail(self, session_id: str) -> None:
        if not session_id:
            return
        md_text = HistoryManager.get_session_markdown(session_id)
        self.query_one("#detail-markdown", Markdown).update(md_text)

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_id and event.option_id != "none":
            self.selected_session_id = str(event.option_id)
            self._show_detail(self.selected_session_id)

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        if event.option_id and event.option_id != "none":
            self.selected_session_id = str(event.option_id)
            self._show_detail(self.selected_session_id)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id in ("btn_back", "btn_close"):
            self.action_dismiss_modal()
        elif btn_id == "btn_delete_one":
            self.action_delete_current()
        elif btn_id == "btn_clear_all":
            self.action_clear_all()

    def action_dismiss_modal(self) -> None:
        self.dismiss(True)

    def action_delete_current(self) -> None:
        if self.selected_session_id:
            HistoryManager.delete_session(self.selected_session_id)
            self._refresh_list()

    def action_clear_all(self) -> None:
        HistoryManager.clear_all_sessions()
        self._refresh_list()
