import time
from typing import Optional, Dict, Any
from textual.containers import ScrollableContainer
from textual.widgets import Static, Collapsible
from core.memory import AgentMessage


class AgentLogPanel(ScrollableContainer):
    """实时流式 AI 对话面板 (使用原生 Collapsible 实现 100% 可点击展开深度思考 + 智能贴底滚轮浏览)"""

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
        color: #e2e8f0;
        background: #090d16;
        padding: 1 1;
        margin: 0 0;
        max-height: 25;
        overflow-y: scroll;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._current_stream_sender_id: Optional[str] = None
        self._current_stream_widget: Optional[Static] = None
        self._current_thinking_widget: Optional[Collapsible] = None
        self._current_thinking_body: Optional[Static] = None
        self._current_thinking_text: str = ""
        self._current_stream_content: str = ""

    def on_mount(self) -> None:
        self.mount(Static("[bold green]🌟 OpenCode 多 API & 多 Agent 自定义协同平台已就绪！[/bold green]\n"))

    def _smart_scroll_end(self) -> None:
        """智能贴底：仅当用户处于最底部附近时自动滚到底；若用户向上滑动滚轮浏览历史，不强行拖拽"""
        try:
            if self.scroll_offset.y >= max(0, self.max_scroll_y - 4):
                self.scroll_end(animate=False)
        except Exception:
            pass

    def write(self, text: str, scroll_end: bool = True) -> None:
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
        """处理流式 Token（原生 Collapsible 思考折叠与正文打字机）"""
        slot_id = data.get("slot_id", "")
        sender_name = data.get("sender_name", "Agent")
        sender_icon = data.get("sender_icon", "🤖")
        token = data.get("token", "")
        is_thinking = bool(data.get("is_thinking", False))

        if not token:
            return

        # 检查是否切换了发言角色
        if self._current_stream_sender_id != slot_id:
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
            # 1. 深度思考流式输出 (使用官方原生 Collapsible)
            self._current_thinking_text += token
            if self._current_thinking_widget is None:
                self._current_thinking_body = Static(
                    f"[dim]{self._current_thinking_text}[/dim] [blink bright_magenta]▌[/blink bright_magenta]",
                    classes="thinking-body"
                )
                self._current_thinking_widget = Collapsible(
                    self._current_thinking_body,
                    title=f"💭 Thinking (深度思考中 · {len(self._current_thinking_text)} 字)...",
                    collapsed=True,
                )
                self.mount(self._current_thinking_widget)
            else:
                self._current_thinking_body.update(
                    f"[dim]{self._current_thinking_text}[/dim] [blink bright_magenta]▌[/blink bright_magenta]"
                )
                self._current_thinking_widget.title = f"💭 Thinking (深度思考中 · {len(self._current_thinking_text)} 字)..."
            
            self._smart_scroll_end()
        else:
            # 2. 正文流式打字输出
            if self._current_thinking_widget is not None and self._current_thinking_body is not None:
                self._current_thinking_body.update(f"[dim]{self._current_thinking_text}[/dim]")
                self._current_thinking_widget.title = f"💭 Thinking (思考完毕 · 共 {len(self._current_thinking_text)} 字)"
                self._current_thinking_widget = None
                self._current_thinking_body = None

            if self._current_stream_widget is not None:
                self._current_stream_content += token
                self._current_stream_widget.update(
                    f"{self._current_stream_content} [blink bold bright_green]▌[/blink bold bright_green]"
                )
                self._smart_scroll_end()
            else:
                self._current_stream_content = token
                new_widget = Static(
                    f"{self._current_stream_content} [blink bold bright_green]▌[/blink bold bright_green]"
                )
                self._current_stream_widget = new_widget
                self.mount(new_widget)
                self._smart_scroll_end()

    def append_message(self, msg: AgentMessage) -> None:
        """追加结构化消息或锁定当前发言"""
        sender_badge = f"[bold #38bdf8]{msg.sender_icon} {msg.sender_name}[/bold #38bdf8]"
        time_str = time.strftime("%H:%M:%S", time.localtime(msg.timestamp))

        # 若是刚才已流式打字输出完的正文
        if msg.msg_type in ("text", "thought") and self._current_stream_sender_id == msg.sender_id:
            if self._current_thinking_widget is not None and self._current_thinking_body is not None:
                final_t = msg.thinking_content or self._current_thinking_text
                self._current_thinking_body.update(f"[dim]{final_t}[/dim]")
                self._current_thinking_widget.title = f"💭 Thinking (思考完毕 · 共 {len(final_t)} 字)"
            elif msg.thinking_content.strip():
                c_body = Static(f"[dim]{msg.thinking_content.strip()}[/dim]", classes="thinking-body")
                c_w = Collapsible(c_body, title=f"💭 Thinking (思考完毕 · 共 {len(msg.thinking_content)} 字)", collapsed=True)
                self.mount(c_w)

            if self._current_stream_widget is not None:
                self._current_stream_widget.update(f"{msg.content}\n")
            elif msg.content.strip():
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
            self._current_thinking_body.update(f"[dim]{self._current_thinking_text}[/dim]")
            self._current_thinking_widget.title = f"💭 Thinking (思考完毕 · 共 {len(self._current_thinking_text)} 字)"
        if self._current_stream_widget is not None:
            self._current_stream_widget.update(f"{self._current_stream_content}\n")

        self._current_stream_sender_id = None
        self._current_stream_widget = None
        self._current_thinking_widget = None
        self._current_thinking_body = None
        self._current_thinking_text = ""
        self._current_stream_content = ""

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
                c_body = Static(f"[dim]{msg.thinking_content.strip()}[/dim]", classes="thinking-body")
                c_w = Collapsible(c_body, title=f"💭 Thinking (思考完毕 · 共 {len(msg.thinking_content)} 字)", collapsed=True)
                self.mount(c_w)
            self.mount(Static(f"\n[dim]{time_str}[/dim] {sender_badge}:\n{msg.content}\n"))

        self._smart_scroll_end()
