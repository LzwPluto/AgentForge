import json
import logging
import re
from typing import List, Dict, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field
import openai
from openai import AsyncOpenAI

from config import config, APIProviderConfig, AgentSlotConfig

logger = logging.getLogger(__name__)


@dataclass
class ToolCallRequest:
    """LLM 发起的工具调用请求"""
    id: str
    name: str
    arguments: Dict[str, Any]
    raw_arguments_str: str


@dataclass
class LLMResponse:
    """LLM 响应统一结构 (包含深度思考内容与最终发言)"""
    content: str
    thinking_content: str = ""
    tool_calls: List[ToolCallRequest] = field(default_factory=list)
    finish_reason: Optional[str] = None
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0


class LLMClient:
    """支持多 API 供应商实例池的异步通用 LLM 客户端"""

    _pool: Dict[str, AsyncOpenAI] = {}

    @classmethod
    def get_client(cls, base_url: str, api_key: str) -> AsyncOpenAI:
        """从实例池获取或新建 AsyncOpenAI 客户端"""
        cache_key = f"{base_url}|{api_key}"
        if cache_key not in cls._pool:
            key = api_key if api_key.strip() else "sk-dummy-key"
            url = base_url if base_url.strip() else "https://api.deepseek.com/v1"
            cls._pool[cache_key] = AsyncOpenAI(api_key=key, base_url=url)
        return cls._pool[cache_key]

    @classmethod
    def get_client_for_provider(cls, provider: APIProviderConfig) -> AsyncOpenAI:
        return cls.get_client(provider.base_url, provider.api_key)

    @classmethod
    def get_client_for_slot(cls, slot: AgentSlotConfig) -> Tuple[AsyncOpenAI, str]:
        prov = config.get_provider(slot.provider_id)
        if not prov:
            prov = config.providers[0]
        return cls.get_client_for_provider(prov), slot.model

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        provider_id: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: float = 0.2,
        thinking_mode: str = "deep",
        on_token_stream: Optional[Callable[..., None]] = None,
    ) -> LLMResponse:
        """异步调用大模型，支持 reasoning_content 思考过程实时流式捕获与思考程度调节/关闭"""
        if provider_id:
            prov = config.get_provider(provider_id)
            target_url = prov.base_url if prov else (base_url or "https://api.deepseek.com/v1")
            target_key = prov.api_key if prov else (api_key or "")
            target_model = model or (prov.models[0] if prov and prov.models else "deepseek-chat")
        else:
            target_url = base_url or "https://api.deepseek.com/v1"
            target_key = api_key or ""
            target_model = model or "deepseek-chat"

        client = self.get_client(target_url, target_key)

        kwargs: Dict[str, Any] = {
            "model": target_model,
            "messages": messages,
            "temperature": temperature,
        }
        if "o1" in target_model.lower() or "o3" in target_model.lower():
            kwargs["max_completion_tokens"] = 8192
        else:
            kwargs["max_tokens"] = 8192

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"


        if thinking_mode == "off":
            kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
            kwargs["reasoning_effort"] = "low"
        elif thinking_mode == "lite":
            kwargs["extra_body"] = {"thinking": {"type": "enabled", "budget_tokens": 1024}}
            kwargs["reasoning_effort"] = "low"

        if on_token_stream:
            kwargs["stream"] = True
            return await self._stream_chat(client, kwargs, target_model, target_url, on_token_stream, thinking_mode=thinking_mode)
        else:
            return await self._non_stream_chat(client, kwargs, target_model, target_url, thinking_mode=thinking_mode)

    async def _stream_chat(
        self,
        client: AsyncOpenAI,
        kwargs: Dict[str, Any],
        target_model: str,
        target_url: str,
        on_token_stream: Callable[..., None],
        thinking_mode: str = "deep",
    ) -> LLMResponse:
        """流式处理并捕获思考与正文内容"""
        response_content = []
        reasoning_content = []
        tool_calls_dict: Dict[int, Dict[str, Any]] = {}
        finish_reason = None

        def _safe_emit(token: str, is_thinking: bool):
            try:
                on_token_stream(token, is_thinking=is_thinking)
            except TypeError:
                try:
                    on_token_stream(token, is_thinking)
                except TypeError:
                    on_token_stream(token)

        try:
            stream = await client.chat.completions.create(**kwargs)
            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if chunk.choices[0].finish_reason:
                    finish_reason = chunk.choices[0].finish_reason

                # 1. 捕获思考流（若设置为关闭思考，则不向前端发送思考弹窗）
                reasoning = getattr(delta, "reasoning_content", None)
                if reasoning:
                    if thinking_mode != "off":
                        reasoning_content.append(reasoning)
                        _safe_emit(reasoning, is_thinking=True)

                # 2. 捕获常规回复内容流
                if delta.content:
                    response_content.append(delta.content)
                    _safe_emit(delta.content, is_thinking=False)


                # 3. 捕获工具调用
                if delta.tool_calls:
                    for tc_chunk in delta.tool_calls:
                        idx = tc_chunk.index
                        if idx not in tool_calls_dict:
                            tool_calls_dict[idx] = {
                                "id": tc_chunk.id or f"call_{idx}",
                                "name": tc_chunk.function.name if tc_chunk.function else "",
                                "arguments": "",
                            }
                        else:
                            if tc_chunk.id:
                                tool_calls_dict[idx]["id"] = tc_chunk.id
                            if tc_chunk.function and tc_chunk.function.name:
                                tool_calls_dict[idx]["name"] += tc_chunk.function.name

                        if tc_chunk.function and tc_chunk.function.arguments:
                            tool_calls_dict[idx]["arguments"] += tc_chunk.function.arguments

            # 组装工具调用
            tool_calls = []
            for _, tc_data in sorted(tool_calls_dict.items()):
                raw_args = tc_data["arguments"]
                parsed_args = {}
                try:
                    if raw_args.strip():
                        parsed_args = json.loads(raw_args)
                except json.JSONDecodeError:
                    parsed_args = {"raw": raw_args}

                tool_calls.append(
                    ToolCallRequest(
                        id=tc_data["id"],
                        name=tc_data["name"],
                        arguments=parsed_args,
                        raw_arguments_str=raw_args,
                    )
                )

            full_content = "".join(response_content)
            full_thinking = "".join(reasoning_content)

            # 解析并提取 content 中内嵌的 <think> 标签思考内容
            if "<think>" in full_content and "</think>" in full_content:
                m = re.search(r"<think>(.*?)</think>", full_content, flags=re.DOTALL)
                if m:
                    parsed_think = m.group(1).strip()
                    full_thinking = (full_thinking + "\n" + parsed_think) if full_thinking else parsed_think
                    full_content = re.sub(r"<think>.*?</think>", "", full_content, flags=re.DOTALL).strip()

            return LLMResponse(
                content=full_content,
                thinking_content=full_thinking,
                tool_calls=tool_calls,
                finish_reason=finish_reason,
                model=target_model,
            )

        except Exception as e:
            logger.exception(f"流式请求失败: {e}")
            raise e

    async def _non_stream_chat(
        self,
        client: AsyncOpenAI,
        kwargs: Dict[str, Any],
        target_model: str,
        target_url: str,
        thinking_mode: str = "deep",
    ) -> LLMResponse:
        """非流式后备处理"""

        try:
            res = await client.chat.completions.create(**kwargs)
            choice = res.choices[0]
            msg = choice.message

            tool_calls = []
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    raw_args = tc.function.arguments
                    try:
                        parsed_args = json.loads(raw_args) if raw_args else {}
                    except json.JSONDecodeError:
                        parsed_args = {"raw": raw_args}
                    tool_calls.append(
                        ToolCallRequest(
                            id=tc.id,
                            name=tc.function.name,
                            arguments=parsed_args,
                            raw_arguments_str=raw_args,
                        )
                    )

            full_content = msg.content or ""
            full_thinking = getattr(msg, "reasoning_content", "") or ""

            if "<think>" in full_content and "</think>" in full_content:
                m = re.search(r"<think>(.*?)</think>", full_content, flags=re.DOTALL)
                if m:
                    parsed_think = m.group(1).strip()
                    full_thinking = (full_thinking + "\n" + parsed_think) if full_thinking else parsed_think
                    full_content = re.sub(r"<think>.*?</think>", "", full_content, flags=re.DOTALL).strip()

            return LLMResponse(
                content=full_content,
                thinking_content=full_thinking,
                tool_calls=tool_calls,
                finish_reason=choice.finish_reason,
                model=target_model,
                prompt_tokens=res.usage.prompt_tokens if res.usage else 0,
                completion_tokens=res.usage.completion_tokens if res.usage else 0,
            )
        except Exception as e:
            logger.exception(f"非流式请求失败: {e}")
            raise e
