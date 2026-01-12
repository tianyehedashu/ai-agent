"""
LLM Gateway - LLM 网关实现

使用 LiteLLM 统一多模型接口
"""

import json
from collections.abc import AsyncGenerator
from typing import Any

import litellm
import tiktoken
from litellm import acompletion
from pydantic import BaseModel

from app.config import settings
from core.types import Message, ToolCall
from utils.logging import get_logger

logger = get_logger(__name__)


class LLMResponse(BaseModel):
    """LLM 响应"""

    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    finish_reason: str | None = None
    usage: dict[str, int] | None = None


class StreamChunk(BaseModel):
    """流式响应块"""

    content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    finish_reason: str | None = None


class LLMGateway:
    """
    LLM 网关

    统一多模型接口，支持:
    - 同步/异步调用
    - 流式/非流式响应
    - 工具调用
    - 重试与 Fallback
    """

    def __init__(self) -> None:
        # 配置 LiteLLM
        litellm.success_callback = []
        litellm.failure_callback = []

        # 设置 API Keys
        if settings.anthropic_api_key:
            litellm.api_key = settings.anthropic_api_key.get_secret_value()

    async def chat(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict | None = None,
        stream: bool = False,
    ) -> LLMResponse | AsyncGenerator[StreamChunk, None]:
        """
        聊天补全

        Args:
            messages: 消息列表
            model: 模型名称
            temperature: 温度参数
            max_tokens: 最大 token 数
            tools: 工具定义列表
            tool_choice: 工具选择策略
            stream: 是否流式输出

        Returns:
            LLMResponse 或流式生成器
        """
        model = model or settings.default_model

        # 构建请求参数
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }

        # 添加工具
        if tools:
            kwargs["tools"] = tools
            if tool_choice:
                kwargs["tool_choice"] = tool_choice

        # 添加 API Key
        kwargs.update(self._get_api_key(model))

        if stream:
            return self._stream_chat(**kwargs)
        else:
            return await self._chat(**kwargs)

    async def _chat(self, **kwargs: Any) -> LLMResponse:
        """非流式调用"""
        try:
            response = await acompletion(**kwargs)

            message = response.choices[0].message

            # 解析工具调用
            tool_calls = None
            if message.tool_calls:
                tool_calls = [
                    ToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=self._parse_arguments(tc.function.arguments),
                    )
                    for tc in message.tool_calls
                ]

            return LLMResponse(
                content=message.content,
                tool_calls=tool_calls,
                finish_reason=response.choices[0].finish_reason,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
            )
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise

    async def _stream_chat(self, **kwargs: Any) -> AsyncGenerator[StreamChunk, None]:
        """流式调用"""
        try:
            response = await acompletion(**kwargs)

            tool_calls_buffer: dict[int, dict[str, Any]] = {}

            async for chunk in response:
                delta = chunk.choices[0].delta

                # 处理内容
                content = delta.content if hasattr(delta, "content") else None

                # 处理工具调用
                if hasattr(delta, "tool_calls") and delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in tool_calls_buffer:
                            tool_calls_buffer[idx] = {
                                "id": tc.id or "",
                                "name": "",
                                "arguments": "",
                            }

                        if tc.function:
                            if tc.function.name:
                                tool_calls_buffer[idx]["name"] = tc.function.name
                            if tc.function.arguments:
                                tool_calls_buffer[idx]["arguments"] += tc.function.arguments

                # 检查完成原因
                finish_reason = chunk.choices[0].finish_reason

                yield StreamChunk(
                    content=content,
                    tool_calls=list(tool_calls_buffer.values()) if tool_calls_buffer else None,
                    finish_reason=finish_reason,
                )

        except Exception as e:
            logger.error(f"LLM stream failed: {e}")
            raise

    def _get_api_key(self, model: str) -> dict[str, Any]:
        """获取对应模型的 API Key"""
        if "claude" in model.lower():
            if settings.anthropic_api_key:
                return {"api_key": settings.anthropic_api_key.get_secret_value()}
        elif "gpt" in model.lower() and settings.openai_api_key:
            return {"api_key": settings.openai_api_key.get_secret_value()}

        return {}

    def _parse_arguments(self, arguments: str) -> dict[str, Any]:
        """解析工具参数"""
        try:
            return json.loads(arguments)
        except json.JSONDecodeError:
            return {"raw": arguments}

    def format_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        """格式化消息为 LLM API 格式"""
        formatted = []
        for msg in messages:
            item: dict[str, Any] = {"role": msg.role.value}

            if msg.content:
                item["content"] = msg.content

            if msg.tool_calls:
                item["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": str(tc.arguments),
                        },
                    }
                    for tc in msg.tool_calls
                ]

            if msg.tool_call_id:
                item["tool_call_id"] = msg.tool_call_id

            formatted.append(item)

        return formatted

    async def count_tokens(self, text: str, model: str | None = None) -> int:
        """计算 token 数量"""
        model = model or settings.default_model

        try:
            encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            encoding = tiktoken.get_encoding("cl100k_base")

        return len(encoding.encode(text))
