import re
import json
import asyncio
import logging
from typing import Optional, List, Dict, Any, Tuple

from config import config, AgentSlotConfig
from core.llm_client import LLMClient
from core.memory import SharedMemory, TaskStatus, AgentStatus, EventType, TaskItem
from agents.dynamic_agent import DynamicAgent

logger = logging.getLogger(__name__)


class Orchestrator:
    """通用多 Agent 顺序循环圆桌协同编排引擎 (带多 Agent 在线民主投票共识机制)"""

    def __init__(self, memory: Optional[SharedMemory] = None):
        self.memory = memory or SharedMemory()
        self.llm_client = LLMClient()
        self._running = False
        self._cancel_requested = False
        self._is_paused = False
        self._pause_event = asyncio.Event()
        self._pause_event.set()

    @property
    def is_paused(self) -> bool:
        return self._is_paused

    @property
    def is_running(self) -> bool:
        return self._running

    def pause(self) -> None:
        """中途安全暂停当前工作流"""
        if not self._running or self._is_paused:
            return

        self._is_paused = True
        self._pause_event.clear()

        # 立即将所有启用的槽位状态更新为 PAUSED 并通知 UI
        for s in config.agent_slots:
            if s.enabled:
                self.memory.update_agent_state(s.slot_id, AgentStatus.PAUSED, "暂停挂起中")

        self.memory.log_message(
            sender_id="system",
            content="⏸️ **【工作流已中途暂停】** 圆桌会议已在断点处安全挂起！\n👉 您可输入调整指令并点击 [▶ 调整并继续]，或直接点击继续。",
            msg_type="pause",
        )
        self.memory.publish(EventType.WORKFLOW_PAUSED, None)

    async def resume(self, steering_feedback: str = "") -> None:
        """恢复执行，可携带用户手动调整的方向意见"""
        if not self._is_paused and self._running:
            return

        if steering_feedback.strip():
            self.memory.log_message(
                sender_id="user",
                sender_name="User (方向调整/插话)",
                sender_icon="🧭",
                content=f"💡 **【用户方向调整指导】**:\n{steering_feedback.strip()}",
                msg_type="steering",
            )
        else:
            self.memory.log_message(
                sender_id="system",
                content="▶️ **【已解除暂停】** 圆桌协同接力继续执行...",
                msg_type="handoff",
            )

        self._is_paused = False
        self._pause_event.set()
        self.memory.publish(EventType.WORKFLOW_RESUMED, None)

    def cancel(self) -> None:
        """彻底中止当前协同流程"""
        self._cancel_requested = True
        self.memory.is_cancelled = True
        self._is_paused = False
        self._running = False
        self._pause_event.set()

        # 立即重置所有槽位为 IDLE 待命状态并通知 UI 刷新
        for slot in config.agent_slots:
            self.memory.update_agent_state(slot.slot_id, AgentStatus.IDLE, "任务已终止待命")

        self.memory.log_message(
            sender_id="system",
            content="⏹️ 用户已终止当前圆桌协同任务。",
            msg_type="error",
        )
        self.memory.publish(EventType.GOAL_FAILED, "用户终止协同任务")



    async def _wait_if_paused(self) -> bool:
        """检查并等待暂停解除"""
        if self._is_paused:
            await self._pause_event.wait()
        return not self._cancel_requested

    async def _conduct_consensus_vote(
        self,
        agents_map: Dict[str, DynamicAgent],
        enabled_slots: List[AgentSlotConfig],
        goal: str,
        round_idx: int,
    ) -> bool:
        """执行全员在线民主投票裁决：所有在场 Agent 依次投票评估是否可以结束"""
        if len(enabled_slots) == 1:
            return True

        self.memory.log_message(
            sender_id="system",
            content=(
                f"🗳️ ═════════ 启动【圆桌全员在线表决】(第 {round_idx} 轮) ═════════\n"
                f"在场 {len(enabled_slots)} 位成员将依次对当前成果进行综合评估，民主投票判定是否达成目标！"
            ),
            msg_type="vote",
        )

        votes: Dict[str, Tuple[bool, str]] = {}

        for slot_cfg in enabled_slots:
            if not await self._wait_if_paused():
                return False

            self.memory.update_agent_state(slot_cfg.slot_id, AgentStatus.THINKING, "正在评估与投票...")

            vote_prompt = (
                f"【多智能体全员在线表决阶段】:\n"
                f"🎯 用户总目标是: 【{goal}】\n"
                f"请回顾群聊中场内所有成员至今的全部发言、已编写/修改的文件与最新成果。\n"
                f"作为【{slot_cfg.name}】，请客观评估当前成果是否已经圆满达标、可以结束协同？\n\n"
                f"请以极精炼的 1~2 句话给出理由，并在回复末尾必须明确输出二选一：\n"
                f"👉 若认为目标已达成无须再修改，请输出: 【投票: 同意结束】\n"
                f"👉 若认为仍有缺陷/需要修改补充，请输出: 【投票: 继续修改】（并简述下一轮需要改什么）"
            )

            vote_messages = self.memory.get_shared_llm_messages_for_agent(
                current_slot_id=slot_cfg.slot_id,
                system_prompt=slot_cfg.system_prompt + "\n你现在作为圆桌评审委员进行共识表决。",
            )
            vote_messages.append({"role": "user", "content": vote_prompt})

            try:
                res = await self.llm_client.chat(
                    messages=vote_messages,
                    tools=None,
                    provider_id=slot_cfg.provider_id,
                    model=slot_cfg.model,
                )
                vote_text = (res.content or "").strip()
            except Exception as e:
                vote_text = f"投票评估异常: {e} 【投票: 同意结束】"

            is_agree = ("同意结束" in vote_text) and ("继续修改" not in vote_text)
            votes[slot_cfg.slot_id] = (is_agree, vote_text)

            badge_txt = "✅ 赞成结束" if is_agree else "❌ 提议继续"
            self.memory.log_message(
                sender_id=slot_cfg.slot_id,
                sender_name=slot_cfg.name,
                sender_icon=slot_cfg.icon,
                content=f"🗳️ 【表决结果: {badge_txt}】\n{vote_text}",
                msg_type="vote",
            )

        # 统计投票结果
        agree_count = sum(1 for is_agree, _ in votes.values() if is_agree)
        total_count = len(enabled_slots)

        if agree_count == total_count:
            self.memory.log_message(
                sender_id="system",
                content=f"🎉 **【表决全票通过 ({agree_count}/{total_count})】** 在场所有 AI 成员一致判定目标已圆满达成！",
                msg_type="handoff",
            )
            return True
        else:
            dissent_reasons = []
            for slot_cfg in enabled_slots:
                is_agree, v_txt = votes[slot_cfg.slot_id]
                if not is_agree:
                    dissent_reasons.append(f"- {slot_cfg.icon} {slot_cfg.name}: {v_txt[:100]}")
            
            summary_reasons = "\n".join(dissent_reasons)
            self.memory.log_message(
                sender_id="system",
                content=(
                    f"🔄 **【表决未全票通过 ({agree_count}/{total_count} 同意)】**\n"
                    f"存在以下修改意见:\n{summary_reasons}\n"
                    f"👉 将上述意见自动作为下一轮接力的重点要求，继续推进协同！"
                ),
                msg_type="handoff",
            )
            return False

    async def run_goal(self, goal: str) -> bool:
        """启动顺序循环多 Agent 圆桌接力协同 (结合全员民主投票共识)"""
        if self._running:
            logger.warning("已有正在运行的工作流")
            return False

        self._running = True
        self._cancel_requested = False
        self.memory.is_cancelled = False
        self._is_paused = False
        self._pause_event.set()
        
        self.memory.set_goal(goal)
        self.memory.sync_slots_from_config()


        enabled_slots = config.get_enabled_slots()
        if not enabled_slots:
            self.memory.log_message(
                sender_id="system",
                content="❌ 当前未启用任何成员槽位！请按 F1 打开设置至少启用 1 个成员。",
                msg_type="error",
            )
            self._running = False
            return False

        try:
            agents_map: Dict[str, DynamicAgent] = {
                slot.slot_id: DynamicAgent(slot, self.memory, self.llm_client)
                for slot in enabled_slots
            }

            for slot in enabled_slots:
                self.memory.add_task(
                    title=f"{slot.icon} {slot.name} 接力协同",
                    description=slot.system_prompt[:60] + "...",
                    assigned_slot_id=slot.slot_id,
                    assigned_name=slot.name,
                )

            order_desc = " ➔ ".join([f"{s.icon} {s.name}" for s in enabled_slots])
            self.memory.log_message(
                sender_id="system",
                content=(
                    f"🎉 **【多 Agent 圆桌协同启动】**\n"
                    f"👥 在场成员 (共 {len(enabled_slots)} 位): {order_desc}\n"
                    f"🔄 协同机制: 全员全量工具开放，顺序循环轮流发言，民主投票共识终结。\n"
                    f"🎯 协同总目标: {goal}"
                ),
                msg_type="handoff",
            )

            # ----------------------------------------------------
            # 顺序循环执行流水线 (Sequential Round-Robin Loop)
            # ----------------------------------------------------
            max_rounds = config.max_loops_per_task or 10
            self.memory.max_rounds = max_rounds
            round_idx = 0
            goal_achieved = False

            while round_idx < max_rounds and not goal_achieved:
                round_idx += 1
                self.memory.current_round = round_idx
                self.memory.publish(EventType.ROUND_UPDATED, {
                    "round": round_idx,
                    "max_rounds": max_rounds,
                })

                if not await self._wait_if_paused():
                    break

                self.memory.log_message(
                    sender_id="system",
                    content=f"🔄 ── 进入圆桌协同【第 {round_idx}/{max_rounds} 轮】接力 ──",
                    msg_type="handoff",
                )

                any_proposed_finish = False

                # 按槽位配置的绝对顺序依次轮流发言
                for slot_cfg in enabled_slots:
                    if not await self._wait_if_paused():
                        break

                    agent = agents_map[slot_cfg.slot_id]
                    self.memory.current_speaker = slot_cfg.name

                    for s in enabled_slots:
                        if s.slot_id == slot_cfg.slot_id:
                            self.memory.update_agent_state(s.slot_id, AgentStatus.SPEAKING, f"第 {round_idx}/{max_rounds} 轮发言中...")
                        else:
                            self.memory.update_agent_state(s.slot_id, AgentStatus.IDLE, "倾听记录中...")

                    self.memory.publish(EventType.ROUND_UPDATED, {
                        "round": round_idx,
                        "max_rounds": max_rounds,
                        "speaker": slot_cfg.name,
                    })

                    response_text = await agent.step_in_group(max_tool_iterations=8)

                    if "【目标已达成】" in response_text or "【任务完成】" in response_text or "【提议结束】" in response_text:
                        any_proposed_finish = True

                if not await self._wait_if_paused():
                    break

                # 每一轮各成员发言接力完成后，若有成员提议结束或已满1轮，启动全员民主表决！
                if any_proposed_finish or round_idx >= 1:
                    vote_passed = await self._conduct_consensus_vote(agents_map, enabled_slots, goal, round_idx)
                    if vote_passed:
                        goal_achieved = True
                        break

            # ----------------------------------------------------
            # 阶段总结交付与历史会话自动归档
            # ----------------------------------------------------
            if not self._cancel_requested:
                for t in self.memory.tasks:
                    self.memory.update_task_status(t.id, TaskStatus.COMPLETED, "圆桌轮次协同完成")

                self.memory.publish(EventType.GOAL_COMPLETED, "多 Agent 圆桌协同圆满达成目标！")
                self.memory.log_message(
                    sender_id="system",
                    content=f"🏁 **【多 Agent 协同圆满完成】** 共进行了 {round_idx} 轮接力打磨，成果已就绪！",
                    msg_type="handoff",
                )
                success_flag = True
            else:
                self.memory.publish(EventType.GOAL_FAILED, "操作被中止")
                success_flag = False

            try:
                from core.history_manager import HistoryManager
                sid = HistoryManager.save_session(
                    user_goal=goal,
                    messages=self.memory.group_chat_history,
                    total_rounds=round_idx,
                    success=success_flag,
                )
                self.memory.log_message(
                    sender_id="system",
                    content=f"💾 **【会话记录已自动归档】** ID: `{sid}` (按 F2 可随时查看或导出 Markdown 纪要)",
                    msg_type="handoff",
                )
            except Exception as e:
                logger.warning(f"归档历史会话异常: {e}")

            return success_flag

        except Exception as e:
            logger.exception("工作流异常终止")
            self.memory.log_message(
                sender_id="system",
                content=f"❌ 工作流异常崩溃: {str(e)}",
                msg_type="error",
            )
            self.memory.publish(EventType.GOAL_FAILED, str(e))
            return False
        finally:
            self._running = False
            self._is_paused = False
            for s in enabled_slots:
                self.memory.update_agent_state(s.slot_id, AgentStatus.IDLE, "就绪待命")
