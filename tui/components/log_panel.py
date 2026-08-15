import time
from typing import Optional, Dict, Any
from textual.containers import ScrollableContainer
from textual.widgets import Static, Collapsible, TextArea
from core.memory import AgentMessage

MAX_VISIBLE_MESSAGES = 25  # 活跃面板最多保留消息块数，多余的自动从顶部清理以防内存过高与卡顿


class AgentLogPanel(ScrollableContainer):
    """高性能实时流式 AI 对话面板 (节流渲染 + 虚拟化思考大文本查看 + 自动顶部剪裁防内存爆炸)"""

    DEFAULT_CSS = """
    AgentLogPanel {
        width: 100%;
        height: 100%;
        border: solid #10b981;
        background: #0f172a;
        padding: 0 1;
        overflow-y: scroll;
    }

    AgentLogPanel Static {
        width: 100%;
        height: auto;
        margin: 0 0;
    }

    Collapsible {
        width: 100%;
        background: #1e1b4b;
        border-left: thick #a855f7;
        margin: 1 0;
        padding: 0 1;
    }

    .thinking-body {
        height: 14;
        background: #090d16;
        color: #94a3b8;
        border: solid #3b0764;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._current_stream_sender_id: Optional[str] = None
        self._current_stream_widget: Optional[Static] = None
        self._current_thinking_widget: Optional[Collapsible] = None
        self._current_thinking_body: Optional[TextArea] = None
        self._current_thinking_text: str = ""
        self._current_stream_content: str = ""
        self._last_thinking_flush: float = 0.0
        self._last_stream_flush: float = 0.0

    def on_mount(self) -> None:
        self.mount(Static("[bold green]🌟 OpenCode 多 API & 多 Agent 自定义协同平台已就绪！[/bold green]\n"))

    def _prune_old_messages(self) -> None:
        """自动从顶部清理多余历史消息，保持视口极速流畅与轻量内存"""
        try:
            while len(self.children) > MAX_VISIBLE_MESSAGES:
                first = self.children[0]
                if first not in (self._current_stream_widget, self._current_thinking_widget):
                    first.remove()
                else:
                    break
        except Exception:
            pass

    def _smart_scroll_end(self) -> None:
        """智能贴底滚动：用户滚轮向上查阅历史时不强行拖拽"""
        try:
            if self.scroll_offset.y >= max(0, self.max_scroll_y - 4):
                self.scroll_end(animate=False)
        except Exception:
            pass

    def write(self, text: str, scroll_end: bool = True) -> None:
        self._prune_old_messages()
        w = Static(text)
        self.mount(w)
        if scroll_end:
            self._smart_scroll_end()

    def clear(self) -> None:
        self._current_stream_sender_id = None
        self._current_stream_widget = None
        self._current_thinking_widget = None
        self._current_thinking_body = None
        self._current_thinking_text = ""
        self._current_stream_content = ""
        self.remove_children()

    def handle_stream_token(self, data: Dict[str, Any]) -> None:
        """处理流式 Token (节流刷新 + 高性能虚拟化思考查看器)"""
        slot_id = data.get("slot_id", "")
        sender_name = data.get("sender_name", "Agent")
        sender_icon = data.get("sender_icon", "🤖")
        token = data.get("token", "")
        is_thinking = bool(data.get("is_thinking", False))

        if not token:
            return

        now = time.time()

        # 检查是否切换了发言角色
        if self._current_stream_sender_id != slot_id:
            self._prune_old_messages()
            time_str = time.strftime("%H:%M:%S")
            sender_badge = f"[bold #38bdf8]{sender_icon} {sender_name}[/bold #38bdf8]"
            self.mount(Static(f"\n[dim]{time_str}[/dim] {sender_badge}:"))
            self._current_stream_sender_id = slot_id
            self._current_stream_content = ""
            self._current_stream_widget = None
            self._current_thinking_widget = None
            self._current_thinking_body = None
            self._current_thinking_text = ""

        if is_thinking:
            # 1. 深度思考流式输出 (使用 TextArea 虚拟化大文本控件，承受 50k+ 字不卡顿)
            self._current_thinking_text += token
            if self._current_thinking_widget is None:
                self._prune_old_messages()
                self._current_thinking_body = TextArea(
                    self._current_thinking_text,
                    read_only=True,
                    show_line_numbers=False,
                    classes="thinking-body",
                )
                self._current_thinking_widget = Collapsible(
                    self._current_thinking_body,
                    title=f"💭 Thinking (深度思考中 · {len(self._current_thinking_text)} 字)...",
                    collapsed=True,
                )
                self.mount(self._current_thinking_widget)
                self._last_thinking_flush = now
            else:
                # 节流刷新：每 60ms 刷新一次 UI，保障流畅度
                if now - self._last_thinking_flush > 0.06:
                    self._current_thinking_body.load_text(self._current_thinking_text)
                    self._current_thinking_widget.title = f"💭 Thinking (深度思考中 · {len(self._current_thinking_text)} 字)..."
                    self._last_thinking_flush = now
            
            self._smart_scroll_end()
        else:
            # 2. 正文流式打字输出
            if self._current_thinking_widget is not None and self._current_thinking_body is not None:
                self._current_thinking_body.load_text(self._current_thinking_text)
                self._current_thinking_widget.title = f"💭 Thinking (思考完毕 · 共 {len(self._current_thinking_text)} 字)"
                self._current_thinking_widget = None
                self._current_thinking_body = None

            self._current_stream_content += token
            if self._current_stream_widget is None:
                self._prune_old_messages()
                new_widget = Static(
                    f"{self._current_stream_content} [blink bold bright_green]▌[/blink bold bright_green]"
                )
                self._current_stream_widget = new_widget
                self.mount(new_widget)
                self._last_stream_flush = now
            else:
                # 节流刷新
                if now - self._last_stream_flush > 0.05:
                    self._current_stream_widget.update(
                        f"{self._current_stream_content} [blink bold bright_green]▌[/blink bold bright_green]"
                    )
                    self._last_stream_flush = now

            self._smart_scroll_end()

    def append_message(self, msg: AgentMessage) -> None:
        """追加结构化消息或锁定当前发言"""
        sender_badge = f"[bold #38bdf8]{msg.sender_icon} {msg.sender_name}[/bold #38bdf8]"
        time_str = time.strftime("%H:%M:%S", time.localtime(msg.timestamp))

        # 若是刚才已流式打字输出完的正文
        if msg.msg_type in ("text", "thought") and self._current_stream_sender_id == msg.sender_id:
            if self._current_thinking_widget is not None and self._current_thinking_body is not None:
                final_t = msg.thinking_content or self._current_thinking_text
                self._current_thinking_body.load_text(final_t)
                self._current_thinking_widget.title = f"💭 Thinking (思考完毕 · 共 {len(final_t)} 字)"
            elif msg.thinking_content.strip():
                self._prune_old_messages()
                c_body = TextArea(msg.thinking_content.strip(), read_only=True, show_line_numbers=False, classes="thinking-body")
                c_w = Collapsible(c_body, title=f"💭 Thinking (思考完毕 · 共 {len(msg.thinking_content)} 字)", collapsed=True)
                self.mount(c_w)

            if self._current_stream_widget is not None:
                self._current_stream_widget.update(f"{msg.content}\n")
            elif msg.content.strip():
                self._prune_old_messages()
                self.mount(Static(f"{msg.content}\n"))

            self._current_stream_sender_id = None
            self._current_stream_widget = None
            self._current_thinking_widget = None
            self._current_thinking_body = None
            self._current_thinking_text = ""
            self._current_stream_content = ""
            self._smart_scroll_end()
            return

        # 其它消息重置流式状态
        if self._current_thinking_widget is not None and self._current_thinking_body is not None:
            self._current_thinking_body.load_text(self._current_thinking_text)
            self._current_thinking_widget.title = f"💭 Thinking (思考完毕 · 共 {len(self._current_thinking_text)} 字)"
        if self._current_stream_widget is not None:
            self._current_stream_widget.update(f"{self._current_stream_content}\n")

        self._current_stream_sender_id = None
        self._current_stream_widget = None
        self._current_thinking_widget = None
        self._current_thinking_body = None
        self._current_thinking_text = ""
        self._current_stream_content = ""

        self._prune_old_messages()

        # 根据消息类型渲染结构化面板
        if msg.msg_type == "tool_call":
            self.mount(Static(f"\n[dim]{time_str}[/dim] {sender_badge} [cyan]{msg.content}[/cyan]"))
        elif msg.msg_type == "tool_result":
            self.mount(Static(f"[dim]{time_str}[/dim] {sender_badge} [dim cyan]{msg.content}[/dim cyan]\n"))
        elif msg.msg_type == "error":
            self.mount(Static(f"\n[dim]{time_str}[/dim] {sender_badge} [bold red]{msg.content}[/bold red]\n"))
        elif msg.msg_type == "handoff":
            self.mount(Static(f"\n[bold yellow]───────── {msg.content} ─────────[/bold yellow]"))
        elif msg.msg_type == "vote":
            self.mount(Static(f"\n[bold black on bright_magenta] 🗳️ 在线表决 [/bold black on bright_magenta] {sender_badge}\n[bright_magenta]{msg.content}[/bright_magenta]\n"))
        elif msg.msg_type == "pause":
            self.mount(Static(f"\n[bold black on yellow] ⏸️ 暂停拦截 [/bold black on yellow] [yellow]{msg.content}[/yellow]\n"))
        elif msg.msg_type == "steering":
            self.mount(Static(f"\n[bold black on bright_cyan] 🧭 方向调整 [/bold black on bright_cyan] [bright_cyan]{msg.content}[/bright_cyan]\n"))
        elif msg.msg_type == "goal":
            self.mount(Static(f"\n[bold bright_cyan]{'='*50}\n{msg.content}\n{'='*50}[/bold bright_cyan]\n"))
        else:
            if msg.thinking_content.strip():
                c_body = TextArea(msg.thinking_content.strip(), read_only=True, show_line_numbers=False, classes="thinking-body")
                c_w = Collapsible(c_body, title=f"💭 Thinking (思考完毕 · 共 {len(msg.thinking_content)} 字)", collapsed=True)
                self.mount(c_w)
            self.mount(Static(f"\n[dim]{time_str}[/dim] {sender_badge}:\n{msg.content}\n"))

        self._smart_scroll_end()
