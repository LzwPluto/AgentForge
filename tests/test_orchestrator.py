import pytest
from config import config, APIProviderConfig, AgentSlotConfig
from core.memory import SharedMemory, TaskStatus, AgentStatus, EventType


def test_multi_provider_and_slots_config():
    # 1. 测试默认 5 槽位存在
    assert len(config.agent_slots) == 5
    assert len(config.providers) >= 3

    # 2. 测试禁用部分槽位
    config.agent_slots[0].enabled = True
    config.agent_slots[1].enabled = True
    config.agent_slots[2].enabled = True
    config.agent_slots[3].enabled = False  # 禁用 Slot 4
    config.agent_slots[4].enabled = False  # 禁用 Slot 5

    enabled_slots = config.get_enabled_slots()
    assert len(enabled_slots) == 3

    # 3. 同步到 SharedMemory
    mem = SharedMemory()
    mem.sync_slots_from_config()

    assert mem.agent_states["slot_1"]["status"] == AgentStatus.IDLE
    assert mem.agent_states["slot_4"]["status"] == AgentStatus.DISABLED
    assert mem.agent_states["slot_5"]["status"] == AgentStatus.DISABLED

    # 恢复启用
    config.agent_slots[3].enabled = True
    config.agent_slots[4].enabled = True


def test_shared_memory_dynamic_tasks():
    mem = SharedMemory()
    task = mem.add_task(
        title="编写算法模块",
        description="编写快速排序",
        assigned_slot_id="slot_3",
        assigned_name="Coder (全栈编码专家)",
    )
    assert task.assigned_slot_id == "slot_3"
    assert task.status == TaskStatus.PENDING

    mem.update_task_status(task.id, TaskStatus.IN_PROGRESS)
    assert mem.tasks[0].status == TaskStatus.IN_PROGRESS

    mem.update_task_status(task.id, TaskStatus.COMPLETED, "已实现 quicksort.py")
    assert mem.tasks[0].status == TaskStatus.COMPLETED
    assert mem.tasks[0].result_summary == "已实现 quicksort.py"


def test_thinking_process_isolation():
    mem = SharedMemory()
    mem.group_chat_history.clear()
    
    # 模拟 slot_1 发送了一条包含思考过程的消息
    mem.log_message(
        sender_id="slot_1",
        sender_name="作家",
        sender_icon="✍️",
        content="这是正式创作的章节内容",
        thinking_content="这是作家专属的内部深度思考过程：大纲设计、心理推演",
        msg_type="thought",
    )
    
    # 1. 默认状态：全局与槽位均开启思考隔离
    config.isolate_all_thinking = True
    config.get_slot("slot_1").isolate_thinking = True
    
    # slot_2 查看上下文
    msgs_for_slot_2 = mem.get_shared_llm_messages_for_agent("slot_2", "审核员系统提示")
    # slot_2 收到的 user message 中，应该只有正式回复，绝不包含深度思考过程
    other_msg = next(m for m in msgs_for_slot_2 if m["role"] == "user")
    assert "这是正式创作的章节内容" in other_msg["content"]
    assert "内部深度思考过程" not in other_msg["content"]
    
    # 2. 当全局与该槽位均关闭隔离时，思考过程会被透传
    config.isolate_all_thinking = False
    config.get_slot("slot_1").isolate_thinking = False
    
    msgs_for_slot_2_unisolated = mem.get_shared_llm_messages_for_agent("slot_2", "审核员系统提示")
    other_msg_unisolated = next(m for m in msgs_for_slot_2_unisolated if m["role"] == "user")
    assert "这是正式创作的章节内容" in other_msg_unisolated["content"]
    assert "内部深度思考过程" in other_msg_unisolated["content"]
    
    # 恢复默认隔离
    config.isolate_all_thinking = True
    config.get_slot("slot_1").isolate_thinking = True

