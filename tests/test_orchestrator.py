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
