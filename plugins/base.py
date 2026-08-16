"""AgentForge Multi-Agent Plugin Extension Framework
Provides hook specifications and registration for external plugins, tools, and event listeners.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger("agentforge.plugins")


class PluginMetadata(BaseModel):
    """插件元数据定义"""
    id: str = Field(description="插件唯一标识")
    name: str = Field(description="插件展示名称")
    version: str = Field(default="1.0.0", description="版本号")
    author: str = Field(default="AgentForge", description="作者")
    description: str = Field(description="功能简述")
    icon: str = Field(default="🧩", description="图标 Emoji")
    enabled: bool = Field(default=False, description="是否已启用")
    has_settings: bool = Field(default=True, description="是否包含独立配置项")
    settings: Dict[str, Any] = Field(default_factory=dict, description="插件配置项")


class BasePlugin:
    """所有 AgentForge 扩展插件的基类"""
    metadata: PluginMetadata

    def __init__(self, metadata: Optional[PluginMetadata] = None):
        if metadata:
            self.metadata = metadata

    async def on_enable(self) -> None:
        """插件被启用时的钩子回调"""
        pass

    async def on_disable(self) -> None:
        """插件被禁用时的钩子回调"""
        pass

    async def on_agent_before_speak(self, slot_id: str, prompt: str) -> str:
        """在 Agent 发言前拦截或丰富 Prompt"""
        return prompt

    async def on_agent_after_speak(self, slot_id: str, response: str) -> str:
        """在 Agent 发言完成后进行后处理"""
        return response

    async def on_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """拦截或修改工具调用参数"""
        return arguments

    def get_additional_tools(self) -> List[Dict[str, Any]]:
        """为 AI Agent 注入新的自定义沙箱工具定义"""
        return []
