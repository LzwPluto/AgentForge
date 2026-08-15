import os
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

from config import PROJECT_ROOT, config
from core.memory import AgentMessage

HISTORY_DIR = PROJECT_ROOT / "history"
INDEX_FILE = HISTORY_DIR / "sessions_index.json"


class HistoryManager:
    """多 Agent 历史对话与协同成果持久化管理与删除工具"""

    @classmethod
    def _ensure_dir(cls) -> Path:
        HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        return HISTORY_DIR

    @classmethod
    def _load_index(cls) -> List[Dict[str, Any]]:
        cls._ensure_dir()
        if INDEX_FILE.exists():
            try:
                with open(INDEX_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    @classmethod
    def _save_index(cls, index_data: List[Dict[str, Any]]) -> None:
        cls._ensure_dir()
        try:
            with open(INDEX_FILE, "w", encoding="utf-8") as f:
                json.dump(index_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[Warn] 保存历史索引失败: {e}")

    @classmethod
    def save_session(
        cls,
        user_goal: str,
        messages: List[AgentMessage],
        total_rounds: int = 1,
        success: bool = True,
    ) -> str:
        """持久化归档一次完整的协同对话（生成 JSON 数据与 Markdown 会议纪要）"""
        cls._ensure_dir()
        now = time.time()
        session_id = time.strftime("%Y%m%d_%H%M%S", time.localtime(now))
        date_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now))

        # 1. 结构化 JSON 数据
        session_data = {
            "session_id": session_id,
            "timestamp": now,
            "date_str": date_str,
            "user_goal": user_goal,
            "total_rounds": total_rounds,
            "success": success,
            "message_count": len(messages),
            "messages": [msg.model_dump() for msg in messages],
        }

        json_path = HISTORY_DIR / f"session_{session_id}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(session_data, f, ensure_ascii=False, indent=2)

        # 2. 生成人类友好的 Markdown 纪要
        md_lines = [
            f"# OpenCode 多 Agent 协同会话记录\n",
            f"- **会话 ID**: `{session_id}`",
            f"- **归档时间**: `{date_str}`",
            f"- **协同总轮数**: `{total_rounds}` 轮",
            f"- **交付状态**: `{'✔ 达成目标' if success else '❌ 未完成'}`",
            f"- **目标任务**: {user_goal}\n",
            f"---\n",
            f"## 📜 详细全景群聊记录\n",
        ]

        for idx, m in enumerate(messages, 1):
            t_str = time.strftime("%H:%M:%S", time.localtime(m.timestamp))
            badge = f"**{m.sender_icon} {m.sender_name}** (`{m.sender_id}`)"
            
            if m.msg_type == "goal":
                md_lines.append(f"\n### 🎯 【总体目标】\n> {m.content}\n")
            elif m.msg_type == "pause":
                md_lines.append(f"\n> ⏸️ **[暂停记录]** {m.content}\n")
            elif m.msg_type == "steering":
                md_lines.append(f"\n### 🧭 【用户中途方向调整】 ({t_str})\n{m.content}\n")
            elif m.msg_type == "handoff":
                md_lines.append(f"\n---\n#### 🔄 {m.content}\n")
            elif m.msg_type == "tool_call":
                md_lines.append(f"- `[{t_str}]` 🛠️ {badge} 调用工具:\n```text\n{m.content}\n```")
            elif m.msg_type == "tool_result":
                md_lines.append(f"- `[{t_str}]` 📋 工具返回:\n```text\n{m.content[:500]}\n```")
            else:
                md_lines.append(f"\n#### `[{t_str}]` {badge}\n{m.content}\n")

        md_path = HISTORY_DIR / f"session_{session_id}.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.writelines("\n".join(md_lines))

        # 3. 写入索引
        index_list = cls._load_index()
        # 避免重复
        index_list = [it for it in index_list if it.get("session_id") != session_id]
        index_list.insert(0, {
            "session_id": session_id,
            "timestamp": now,
            "date_str": date_str,
            "goal": user_goal[:80] + ("..." if len(user_goal) > 80 else ""),
            "total_rounds": total_rounds,
            "message_count": len(messages),
            "success": success,
            "json_file": f"session_{session_id}.json",
            "md_file": f"session_{session_id}.md",
        })
        cls._save_index(index_list)
        return session_id

    @classmethod
    def list_sessions(cls) -> List[Dict[str, Any]]:
        """获取所有已归档的历史会话列表 (按时间倒序)"""
        return cls._load_index()

    @classmethod
    def get_session_markdown(cls, session_id: str) -> str:
        """读取指定会话的 Markdown 内容"""
        md_file = HISTORY_DIR / f"session_{session_id}.md"
        if md_file.exists():
            try:
                with open(md_file, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception as e:
                return f"读取会话失败: {e}"
        return "未找到对应历史会话文件"

    @classmethod
    def delete_session(cls, session_id: str) -> bool:
        """删除指定历史会话"""
        cls._ensure_dir()
        json_file = HISTORY_DIR / f"session_{session_id}.json"
        md_file = HISTORY_DIR / f"session_{session_id}.md"

        if json_file.exists():
            try:
                json_file.unlink()
            except Exception:
                pass
        if md_file.exists():
            try:
                md_file.unlink()
            except Exception:
                pass

        index_list = cls._load_index()
        index_list = [it for it in index_list if it.get("session_id") != session_id]
        cls._save_index(index_list)
        return True

    @classmethod
    def clear_all_sessions(cls) -> bool:
        """清空删除所有历史会话"""
        cls._ensure_dir()
        index_list = cls._load_index()
        for item in index_list:
            sid = item.get("session_id")
            if sid:
                try:
                    (HISTORY_DIR / f"session_{sid}.json").unlink(missing_ok=True)
                    (HISTORY_DIR / f"session_{sid}.md").unlink(missing_ok=True)
                except Exception:
                    pass
        cls._save_index([])
        return True
