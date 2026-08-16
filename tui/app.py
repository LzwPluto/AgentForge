import asyncio
from typing import Optional

from textual.app import App, ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Header, Footer, Input, Button, Static, Label
from textual.binding import Binding
from textual import work

from config import config
from core.memory import SharedMemory, EventType, AgentMessage, TaskItem, AgentStatus
from core.orchestrator import Orchestrator
from tui.components.task_tree import TaskBoardWidget
from tui.components.agent_card import AgentStatusCardsWidget
from tui.components.log_panel import AgentLogPanel
from tui.components.diff_view import DiffViewerWidget
from tui.components.config_modal import ConfigModal
from tui.components.history_modal import HistoryModal


class AgentForgeApp(App):
    """AgentForge Multi-Agent 协同创作平台主界面 (支持历史会话管理与模型选择联动)"""

    TITLE = "AgentForge Multi-Agent Platform"
    SUB_TITLE = "多 API 驱动 + 顺序循环圆桌接力 + 历史会话管理 + 中途干预"

OpenCodeApp = AgentForgeApp  # 兼容别名
    CSS = """
    Screen {
        background: #0b0f19;
    }

    #header-info {
        height: 1;
        background: #1e293b;
        color: #94a3b8;
        padding: 0 1;
    }

    #top-agents-container {
        height: 6;
        margin-bottom: 0;
    }

    #main-content {
        height: 1fr;
    }

    #left-panel {
        width: 30%;
        height: 100%;
    }

    #right-panel {
        width: 70%;
        height: 100%;
    }

    #log-container {
        height: 65%;
    }

    #diff-container {
        height: 35%;
    }

    #bottom-bar {
        height: 3;
        background: #1e293b;
        padding: 0 1;
        align: left middle;
    }

    #input-goal {
        width: 1fr;
    }

    .action-btn {
        margin-left: 1;
    }
    """

    BINDINGS = [
        Binding("f1", "open_settings", "⚙️ 设置 (F1)", show=True),
        Binding("f2", "open_history", "📜 历史会话 (F2)", show=True),
        Binding("ctrl+p", "toggle_pause", "⏸ 暂停/调整 (Ctrl+P)", show=True),
        Binding("ctrl+c", "cancel_workflow", "⏹ 彻底结束 (Ctrl+C)", show=True),
        Binding("f5", "refresh_all", "🔄 刷新视图", show=True),
        Binding("ctrl+l", "clear_logs", "🧹 清屏", show=True),
        Binding("ctrl+q", "quit", "❌ 退出", show=True),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.memory = SharedMemory()
        self.orchestrator = Orchestrator(self.memory)
        self._workflow_state = "IDLE"  # IDLE | RUNNING | PAUSED

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        
        yield Static("", id="header-info")

        # 5 大 Agent 状态卡片栏
        with Vertical(id="top-agents-container"):
            yield AgentStatusCardsWidget(self.memory, id="agent-cards")

        # 核心双栏工作区
        with Horizontal(id="main-content"):
            with Vertical(id="left-panel"):
                yield TaskBoardWidget(self.memory, id="task-board")

            with Vertical(id="right-panel"):
                with Vertical(id="log-container"):
                    yield AgentLogPanel(id="log-panel")
                with Vertical(id="diff-container"):
                    yield DiffViewerWidget(id="diff-viewer")

        # 底部目标输入栏与操作按钮
        with Horizontal(id="bottom-bar"):
            yield Input(
                placeholder="💡 输入协同目标 (例如: 联合创作科幻小说第一章，作家起草，审核员润色)...",
                id="input-goal",
            )
            yield Button("🚀 协同执行", variant="success", id="btn_run", classes="action-btn")
            yield Button("⏸ 暂停/调整", variant="warning", id="btn_pause", classes="action-btn")
            yield Button("⏹ 彻底结束", variant="error", id="btn_cancel", classes="action-btn")
            yield Button("📜 历史", variant="default", id="btn_history", classes="action-btn")
            yield Button("⚙️ 设置", variant="primary", id="btn_settings", classes="action-btn")

        yield Footer()

    def on_mount(self) -> None:
        self.memory.subscribe(self._handle_bus_event)
        self._update_control_bar_state("IDLE")
        self._update_header_info()

        log_p = self.query_one("#log-panel", AgentLogPanel)
        has_key = any(p.api_key and "your-api-key" not in p.api_key for p in config.providers)
        if not has_key:
            log_p.write("[bold yellow]⚠️ 提示：尚未检测到任何有效的 API Key。请按 F1 或点击右下角 [⚙️ 设置] 填入大模型密钥。[/bold yellow]\n")

    def _update_header_info(self) -> None:
        """更新顶部全局轮次与状态信息"""
        try:
            enabled_count = len(config.get_enabled_slots())
            cur_r = self.memory.current_round
            max_r = self.memory.max_rounds
            speaker = self.memory.current_speaker
            
            if cur_r > 0:
                round_str = f"[bold yellow]第 {cur_r}/{max_r} 轮接力[/bold yellow]"
            else:
                round_str = "[green]🟢 空闲就绪[/green]"

            speaker_str = f" · [bold bright_cyan]当前发言: {speaker}[/bold bright_cyan]" if (cur_r > 0 and speaker) else ""

            header_info = self.query_one("#header-info", Static)
            header_info.update(
                f" [bold cyan]轮次进度:[/bold cyan] {round_str}{speaker_str}  |  "
                f"[bold cyan]活跃成员:[/bold cyan] {enabled_count}/5 位  |  "
                f"[bold cyan]默认供应商:[/bold cyan] {config.providers[0].name if config.providers else '-'}  |  "
                f"[bold cyan]工作区:[/bold cyan] {config.workspace_root}"
            )
        except Exception:
            pass

    def _update_control_bar_state(self, state: str) -> None:
        """更新底部控制栏按钮与输入框状态"""
        self._workflow_state = state
        input_w = self.query_one("#input-goal", Input)
        btn_run = self.query_one("#btn_run", Button)
        btn_pause = self.query_one("#btn_pause", Button)
        btn_cancel = self.query_one("#btn_cancel", Button)

        if state == "IDLE":
            input_w.placeholder = "💡 输入协同目标 (例如: 联合创作科幻小说第一章，作家起草，审核员润色)..."
            input_w.disabled = False
            btn_run.display = True
            btn_run.label = "🚀 协同执行"
            btn_run.variant = "success"
            btn_pause.display = False
            btn_cancel.display = False

        elif state == "RUNNING":
            input_w.placeholder = "⏳ 多 Agent 正在轮流接力中... (可随时按 Ctrl+P 或点击右侧 [⏸ 暂停/调整] 介入)"
            input_w.disabled = False
            btn_run.display = False
            btn_pause.display = True
            btn_pause.label = "⏸ 暂停/调整"
            btn_pause.variant = "warning"
            btn_cancel.display = True

        elif state == "PAUSED":
            input_w.placeholder = "💡 请输入方向调整意见 (无输入可直接按回车或点击继续)..."
            input_w.disabled = False
            btn_run.display = True
            btn_run.label = "▶ 调整并继续"
            btn_run.variant = "success"
            btn_pause.display = False
            btn_cancel.display = True

    def _handle_bus_event(self, event_type: EventType, data: any) -> None:
        try:
            if event_type == EventType.TOKEN_STREAM:
                log_p = self.query_one("#log-panel", AgentLogPanel)
                log_p.handle_stream_token(data)
            elif event_type == EventType.MESSAGE_LOGGED:
                log_p = self.query_one("#log-panel", AgentLogPanel)
                log_p.append_message(data)
            elif event_type in (EventType.TASK_ADDED, EventType.TASK_UPDATED):
                board = self.query_one("#task-board", TaskBoardWidget)
                board.refresh_tasks()

            elif event_type == EventType.ROUND_UPDATED:
                self._update_header_info()
                cards = self.query_one("#agent-cards", AgentStatusCardsWidget)
                cards.refresh_cards()
            elif event_type in (EventType.AGENT_STATE_CHANGED, EventType.CONFIG_RELOADED):
                self._update_header_info()
                cards = self.query_one("#agent-cards", AgentStatusCardsWidget)
                cards.refresh_cards()
            elif event_type == EventType.DIFF_UPDATED:
                dv = self.query_one("#diff-viewer", DiffViewerWidget)
                dv.refresh_diff(data.get("file", ""))
            elif event_type == EventType.WORKFLOW_PAUSED:
                self._update_control_bar_state("PAUSED")
                cards = self.query_one("#agent-cards", AgentStatusCardsWidget)
                cards.refresh_cards()
                self._update_header_info()
            elif event_type == EventType.WORKFLOW_RESUMED:
                self._update_control_bar_state("RUNNING")
                cards = self.query_one("#agent-cards", AgentStatusCardsWidget)
                cards.refresh_cards()
                self._update_header_info()
            elif event_type in (EventType.GOAL_COMPLETED, EventType.GOAL_FAILED):
                self._update_control_bar_state("IDLE")
                cards = self.query_one("#agent-cards", AgentStatusCardsWidget)
                cards.refresh_cards()
                board = self.query_one("#task-board", TaskBoardWidget)
                board.refresh_tasks()
                dv = self.query_one("#diff-viewer", DiffViewerWidget)
                dv.refresh_diff()
                self._update_header_info()
        except Exception:
            pass

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "input-goal":
            if self._workflow_state == "IDLE":
                await self._trigger_run()
            elif self._workflow_state == "PAUSED":
                await self._trigger_resume_with_steering()
            elif self._workflow_state == "RUNNING":
                self.orchestrator.pause()
                await self._trigger_resume_with_steering()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id == "btn_run":
            if self._workflow_state == "IDLE":
                await self._trigger_run()
            elif self._workflow_state == "PAUSED":
                await self._trigger_resume_with_steering()
        elif btn_id == "btn_pause":
            self.action_toggle_pause()
        elif btn_id == "btn_cancel":
            self.action_cancel_workflow()
        elif btn_id == "btn_history":
            self.action_open_history()
        elif btn_id == "btn_settings":
            self.action_open_settings()

    async def _trigger_run(self) -> None:
        input_widget = self.query_one("#input-goal", Input)
        goal = input_widget.value.strip()
        if not goal:
            return

        self._update_control_bar_state("RUNNING")
        input_widget.value = ""
        self._current_worker = self.run_orchestrator_worker(goal)

    async def _trigger_resume_with_steering(self) -> None:
        input_widget = self.query_one("#input-goal", Input)
        feedback = input_widget.value.strip()
        input_widget.value = ""
        self._update_control_bar_state("RUNNING")
        await self.orchestrator.resume(steering_feedback=feedback)

    @work(exclusive=True)
    async def run_orchestrator_worker(self, goal: str) -> None:
        try:
            await self.orchestrator.run_goal(goal)
        finally:
            self._update_control_bar_state("IDLE")

    def action_toggle_pause(self) -> None:
        if self._workflow_state == "RUNNING":
            self.orchestrator.pause()
            self._update_header_info()
            try:
                self.query_one("#agent-cards", AgentStatusCardsWidget).refresh_cards()
            except Exception:
                pass
        elif self._workflow_state == "PAUSED":
            asyncio.create_task(self._trigger_resume_with_steering())

    def action_open_settings(self) -> None:
        def _on_modal_close(saved: bool) -> None:
            if saved:
                self.memory.sync_slots_from_config()
                self._update_header_info()
                self.query_one("#agent-cards", AgentStatusCardsWidget).refresh_cards()
                log_p = self.query_one("#log-panel", AgentLogPanel)
                enabled_count = len(config.get_enabled_slots())
                log_p.write(f"[green]✔ 多 API 与角色分工配置已更新！(当前启用 {enabled_count}/5 位成员)[/green]\n")

        self.push_screen(ConfigModal(), _on_modal_close)

    def action_open_history(self) -> None:
        """打开历史会话管理弹窗"""
        self.push_screen(HistoryModal())

    def action_cancel_workflow(self) -> None:
        if self._workflow_state in ("RUNNING", "PAUSED"):
            self.orchestrator.cancel()
            if hasattr(self, "_current_worker") and self._current_worker and not self._current_worker.is_finished:
                try:
                    self._current_worker.cancel()
                except Exception:
                    pass
            self._update_control_bar_state("IDLE")
            for s in config.agent_slots:
                self.memory.update_agent_state(s.slot_id, AgentStatus.IDLE, "已终止待命")
            self._update_header_info()
            try:
                self.query_one("#agent-cards", AgentStatusCardsWidget).refresh_cards()
            except Exception:
                pass



    def action_refresh_all(self) -> None:
        self.memory.sync_slots_from_config()
        self._update_header_info()
        self.query_one("#agent-cards", AgentStatusCardsWidget).refresh_cards()
        self.query_one("#task-board", TaskBoardWidget).refresh_tasks()
        self.query_one("#diff-viewer", DiffViewerWidget).refresh_diff()

    def action_clear_logs(self) -> None:
        self.query_one("#log-panel", AgentLogPanel).clear()
