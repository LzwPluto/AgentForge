import time
from enum import Enum
from typing import List, Dict, Any, Optional, Callable
from pydantic import BaseModel, Field

from config import config, AgentSlotConfig


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"


class AgentStatus(str, Enum):
    IDLE = "IDLE"
    THINKING = "THINKING"
    EXECUTING_TOOL = "EXECUTING_TOOL"
    WAITING = "WAITING"
    SPEAKING = "SPEAKING"  # 轮流发言中
    PAUSED = "PAUSED"      # 中途暂停挂起状态
    ERROR = "ERROR"
    FINISHED = "FINISHED"
    DISABLED = "DISABLED"  # 未启用状态


class AgentRole(str, Enum):
    """预设 Agent 角色标识 (兼容)"""
    LEAD = "lead"
    EXPLORER = "explorer"
    CODER = "coder"
    RUNNER = "runner"
    REVIEWER = "reviewer"
    WRITER = "writer"
    SYSTEM = "system"
    USER = "user"


class TaskItem(BaseModel):
    """任务看板单项"""
    id: str
    title: str
    description: str = ""
    assigned_slot_id: str = "slot_1"
    assigned_name: str = "成员"
    status: TaskStatus = TaskStatus.PENDING
    result_summary: str = ""
    error_message: Optional[str] = None
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


class AgentMessage(BaseModel):
    """通信与思考日志条目"""
    id: str = Field(default_factory=lambda: f"msg_{int(time.time()*1000)}")
    sender_id: str  # slot_1 ~ slot_5 或 "system", "user"
    sender_name: str = ""
    sender_icon: str = "🤖"
    recipient_id: Optional[str] = None
    msg_type: str = "text"  # text | thought | tool_call | tool_result | handoff | error | goal | pause | steering
    content: str
    thinking_content: str = ""  # 深度思考过程 (仅供人类用户在前端监视查看，隔离保护不给其他 AI 角色)
    tool_calls: Optional[List[Any]] = None
    tool_results: Optional[List[Any]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)


class EventType(str, Enum):
    TOKEN_STREAM = "TOKEN_STREAM"
    AGENT_STATE_CHANGED = "AGENT_STATE_CHANGED"
    TASK_ADDED = "TASK_ADDED"
    TASK_UPDATED = "TASK_UPDATED"
    MESSAGE_LOGGED = "MESSAGE_LOGGED"
    DIFF_UPDATED = "DIFF_UPDATED"
    ROUND_UPDATED = "ROUND_UPDATED"        # 轮次更新事件
    GOAL_COMPLETED = "GOAL_COMPLETED"
    GOAL_FAILED = "GOAL_FAILED"
    WORKFLOW_PAUSED = "WORKFLOW_PAUSED"
    WORKFLOW_RESUMED = "WORKFLOW_RESUMED"
    CONFIG_RELOADED = "CONFIG_RELOADED"


class SharedMemory:
    """黑板模式全局全知共享群聊记忆体与事件总线"""

    def __init__(self):
        self.user_goal: str = ""
        self.current_round: int = 0
        self.max_rounds: int = 10
        self.current_speaker: str = ""
        self.is_cancelled: bool = False
        self.tasks: List[TaskItem] = []
        self.messages: List[AgentMessage] = []
        self.group_chat_history: List[AgentMessage] = []
        self.agent_states: Dict[str, Dict[str, Any]] = {}
        self._subscribers: List[Callable[[EventType, Any], None]] = []
        self.sync_slots_from_config()


    def sync_slots_from_config(self) -> None:
        """根据当前配置同步 5 个槽位的状态字典"""
        for i in range(1, 6):
            slot_id = f"slot_{i}"
            slot_cfg = config.get_slot(slot_id)
            if slot_cfg and slot_cfg.enabled:
                self.agent_states[slot_id] = {
                    "slot_id": slot_id,
                    "slot_index": i,
                    "enabled": True,
                    "name": slot_cfg.name,
                    "icon": slot_cfg.icon,
                    "model": slot_cfg.model,
                    "provider_id": slot_cfg.provider_id,
                    "allow_tools": slot_cfg.allow_tools,
                    "status": AgentStatus.IDLE,
                    "current_task": "",
                    "last_action": "就绪待命",
                }
            else:
                self.agent_states[slot_id] = {
                    "slot_id": slot_id,
                    "slot_index": i,
                    "enabled": False,
                    "name": slot_cfg.name if slot_cfg else f"槽位 {i}",
                    "icon": "⚪",
                    "model": slot_cfg.model if slot_cfg else "-",
                    "provider_id": slot_cfg.provider_id if slot_cfg else "-",
                    "allow_tools": False,
                    "status": AgentStatus.DISABLED,
                    "current_task": "",
                    "last_action": "未启用 (Disabled)",
                }


    def subscribe(self, callback: Callable[[EventType, Any], None]) -> None:
        if callback not in self._subscribers:
            self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[EventType, Any], None]) -> None:
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    def publish(self, event_type: EventType, data: Any = None) -> None:
        for sub in list(self._subscribers):
            try:
                sub(event_type, data)
            except Exception as e:
                print(f"[Error in EventBus subscriber]: {e}")

    def set_goal(self, goal: str) -> None:
        self.user_goal = goal
        self.tasks.clear()
        self.messages.clear()
        self.group_chat_history.clear()
        
        goal_msg = AgentMessage(
            sender_id="user",
            sender_name="User (总目标)",
            sender_icon="🎯",
            content=f"开发与创作总目标: {goal}",
            msg_type="goal",
        )
        self.group_chat_history.append(goal_msg)
        self.publish(EventType.MESSAGE_LOGGED, goal_msg)

    def add_task(self, title: str, description: str, assigned_slot_id: str = "slot_1", assigned_name: str = "") -> TaskItem:
        task_id = f"task_{len(self.tasks) + 1}"
        slot_cfg = config.get_slot(assigned_slot_id)
        disp_name = assigned_name or (slot_cfg.name if slot_cfg else assigned_slot_id)
        task = TaskItem(
            id=task_id,
            title=title,
            description=description,
            assigned_slot_id=assigned_slot_id,
            assigned_name=disp_name,
            status=TaskStatus.PENDING,
        )
        self.tasks.append(task)
        self.publish(EventType.TASK_ADDED, task)
        return task

    def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        result_summary: str = "",
        error_message: Optional[str] = None,
    ) -> Optional[TaskItem]:
        for t in self.tasks:
            if t.id == task_id:
                t.status = status
                t.updated_at = time.time()
                if result_summary:
                    t.result_summary = result_summary
                if error_message:
                    t.error_message = error_message
                self.publish(EventType.TASK_UPDATED, t)
                return t
        return None

    def update_agent_state(
        self,
        slot_id: str,
        status: AgentStatus,
        last_action: str = "",
        current_task: str = "",
    ) -> None:
        if slot_id in self.agent_states:
            self.agent_states[slot_id]["status"] = status
            if last_action:
                self.agent_states[slot_id]["last_action"] = last_action
            if current_task:
                self.agent_states[slot_id]["current_task"] = current_task
            self.publish(EventType.AGENT_STATE_CHANGED, {
                "slot_id": slot_id,
                "state": self.agent_states[slot_id],
            })

    def log_message(
        self,
        sender_id: str,
        content: str,
        thinking_content: str = "",
        sender_name: str = "",
        sender_icon: str = "",
        recipient_id: Optional[str] = None,
        msg_type: str = "text",
        tool_calls: Optional[List[Any]] = None,
        tool_results: Optional[List[Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AgentMessage:
        slot_cfg = config.get_slot(sender_id)
        if not sender_name:
            if sender_id == "system":
                sender_name = "System"
                sender_icon = "⚙️"
            elif sender_id == "user":
                sender_name = "User"
                sender_icon = "👤"
            elif slot_cfg:
                sender_name = slot_cfg.name
                sender_icon = slot_cfg.icon

        msg = AgentMessage(
            sender_id=sender_id,
            sender_name=sender_name or sender_id,
            sender_icon=sender_icon or "🤖",
            recipient_id=recipient_id,
            content=content,
            thinking_content=thinking_content,
            msg_type=msg_type,
            tool_calls=tool_calls,
            tool_results=tool_results,
            metadata=metadata or {},
        )
        self.messages.append(msg)
        self.group_chat_history.append(msg)
        self.publish(EventType.MESSAGE_LOGGED, msg)
        return msg

    def get_shared_llm_messages_for_agent(self, current_slot_id: str, system_prompt: str) -> List[Dict[str, Any]]:
        """为当前轮到的 Agent 组装全景群聊上下文"""
        slot_cfg = config.get_slot(current_slot_id)
        my_name = slot_cfg.name if slot_cfg else current_slot_id

        system_intro = (
            f"{system_prompt}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"【多智能体圆桌协作规则】:\n"
            f"1. 你当前正在一个多角色协作实时群聊中，你的身份是:【{slot_cfg.icon if slot_cfg else ''} {my_name}】。\n"
            f"2. 场内所有成员的发言、思考与调用的文件操作结果对全场完全公开透明。\n"
            f"3. 请仔细阅读前序成员的所有产出与反馈，直接承接并推进工作，充分发挥你的专业职责！\n"
            f"4. 你可以使用所有开放的沙箱工具（如 write_file 编写、view_file 查看、edit_file_exact 修改、run_command 执行）。\n"
            f"5. 当你确认团队已彻底达成目标且内容无需再修改时，请在发言末尾包含明确字样【目标已达成】。\n"
            f"6. 【思考与输出规范】: 深度思考是你的内部逻辑推导。在思考结束后，你必须在正文中输出清晰完整的正式回复、方案总结或工具调用，严禁只进行思考而不输出任何正文！\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

        )
        llm_messages = [{"role": "system", "content": system_intro}]

        for msg in self.group_chat_history:
            if msg.sender_id == current_slot_id:
                content_text = msg.content
                if msg.tool_results:
                    for tr in msg.tool_results:
                        out_text = tr.get("output", str(tr)) if isinstance(tr, dict) else str(tr)
                        content_text += f"\n[工具调用结果]:\n{out_text[:400]}"
                llm_messages.append({
                    "role": "assistant",
                    "content": content_text,
                })
            else:
                if msg.sender_id == "user":
                    header = f"👤 【用户/总体目标】"
                elif msg.sender_id == "system":
                    header = f"⚙️ 【系统状态】"
                else:
                    header = f"💬 【{msg.sender_icon} {msg.sender_name} 的发言与产出】"

                body = msg.content
                if msg.tool_results:
                    for tr in msg.tool_results:
                        out_text = tr.get("output", str(tr)) if isinstance(tr, dict) else str(tr)
                        body += f"\n[其调用的工具结果]:\n{out_text[:400]}"

                llm_messages.append({
                    "role": "user",
                    "content": f"{header}:\n{body}",
                })

        return llm_messages

    def reset(self) -> None:
        self.user_goal = ""
        self.tasks.clear()
        self.messages.clear()
        self.group_chat_history.clear()
        self.sync_slots_from_config()
        self.publish(EventType.CONFIG_RELOADED, None)
