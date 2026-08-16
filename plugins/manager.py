import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

from config import PROJECT_ROOT
from plugins.base import BasePlugin, PluginMetadata

logger = logging.getLogger("agentforge.plugins")
PLUGINS_CONFIG_FILE = PROJECT_ROOT / "agentforge_plugins.json"

# 预设官方生态扩展插件
BUILTIN_PLUGINS = [
    PluginMetadata(
        id="web_search_enhancer",
        name="联网搜索与知识增强 (Web Search)",
        version="1.0.2",
        author="AgentForge Ecosystem",
        description="为智能体自动注入实时联网搜索、网页正文提取与最新技术文档检索能力。",
        icon="🔍",
        enabled=False,
        has_settings=True,
        settings={"search_engine": "DuckDuckGo", "max_results": 5}
    ),
    PluginMetadata(
        id="mermaid_chart_live",
        name="Mermaid 架构流程图渲染器 (Live Charts)",
        version="1.1.0",
        author="AgentForge Ecosystem",
        description="自动识别消息中的 mermaid 代码块并实时渲染为高清矢量架构图与时序流程图。",
        icon="📊",
        enabled=True,
        has_settings=False,
        settings={}
    ),
    PluginMetadata(
        id="voice_speech_tts",
        name="角色多重音色语音播报 (Voice TTS)",
        version="1.0.0",
        author="AgentForge Ecosystem",
        description="在多 Agent 轮流发言接力时，为每个槽位分配不同音色的拟人化语音实时朗读输出。",
        icon="🎙️",
        enabled=False,
        has_settings=True,
        settings={"volume": 0.8, "rate": 1.0}
    ),
    PluginMetadata(
        id="vector_memory_rag",
        name="超长工作区向量检索记忆 (Vector RAG)",
        version="0.9.5",
        author="AgentForge Ecosystem",
        description="基于本地 SQLite 向量数据库为海量代码与历史长文建立语义索引与精准召回。",
        icon="🗄️",
        enabled=False,
        has_settings=True,
        settings={"chunk_size": 500, "similarity_top_k": 3}
    ),
    PluginMetadata(
        id="custom_python_hook",
        name="自定义 Python 脚本钩子 (Custom Hook SDK)",
        version="1.0.0",
        author="Developer SDK",
        description="允许在 plugins/scripts/ 目录下编写自定义 Python 钩子脚本，无缝拦截与拓展事件流水线。",
        icon="🛠️",
        enabled=True,
        has_settings=True,
        settings={"script_path": "plugins/scripts/custom_hooks.py"}
    )
]


class PluginManager:
    """AgentForge 插件生命周期与状态管理器"""

    def __init__(self):
        self.plugins: Dict[str, PluginMetadata] = {}
        self.load_plugins()

    def load_plugins(self) -> None:
        """加载插件配置与默认插件"""
        for p in BUILTIN_PLUGINS:
            self.plugins[p.id] = p.model_copy()

        if PLUGINS_CONFIG_FILE.exists():
            try:
                with open(PLUGINS_CONFIG_FILE, "r", encoding="utf-8") as f:
                    saved_data = json.load(f)
                for item in saved_data:
                    pid = item.get("id")
                    if pid in self.plugins:
                        self.plugins[pid].enabled = item.get("enabled", self.plugins[pid].enabled)
                        self.plugins[pid].settings.update(item.get("settings", {}))
                    else:
                        self.plugins[pid] = PluginMetadata.model_validate(item)
            except Exception as e:
                logger.warning(f"读取插件配置异常: {e}")

    def save_plugins(self) -> None:
        """持久化保存插件配置"""
        try:
            data = [p.model_dump() for p in self.plugins.values()]
            with open(PLUGINS_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"保存插件配置失败: {e}")

    def list_plugins(self) -> List[PluginMetadata]:
        return list(self.plugins.values())

    def toggle_plugin(self, plugin_id: str, enabled: Optional[bool] = None) -> Optional[PluginMetadata]:
        if plugin_id in self.plugins:
            p = self.plugins[plugin_id]
            p.enabled = (not p.enabled) if enabled is None else enabled
            self.save_plugins()
            return p
        return None

    def update_plugin_settings(self, plugin_id: str, settings: Dict[str, Any]) -> Optional[PluginMetadata]:
        if plugin_id in self.plugins:
            p = self.plugins[plugin_id]
            p.settings.update(settings)
            self.save_plugins()
            return p
        return None


plugin_manager = PluginManager()
