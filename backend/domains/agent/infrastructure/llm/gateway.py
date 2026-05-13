"""
LLM Gateway - LLM 网关实现

使用 LiteLLM 统一多模型接口

注意：
- 当 settings.gateway_internal_proxy_enabled=True 且能解析到归因 user_id 时，
  本类会优先把调用转发到 AI Gateway 桥接层（GatewayProxyProtocol / GatewayBridge），
  以便统一统计、预算与 Guardrail（含 BYOK 时传入的 api_key/api_base）。
- 直接 LiteLLM 调用作为回退路径（显式关闭 internal proxy、无归因用户、或
  gateway_internal_proxy_fail_closed=False 时桥接失败）。
"""

from collections.abc import AsyncGenerator
from contextlib import suppress
import json
import os
from typing import TYPE_CHECKING, Any

import litellm  # pylint: disable=import-error
from litellm import acompletion, aembedding  # pylint: disable=import-error
from pydantic import BaseModel
import tiktoken

from bootstrap.config import settings as _global_settings
from bootstrap.config_loader import get_app_config
from domains.agent.domain.types import Message, ToolCall
from domains.agent.infrastructure.llm.message_formatter import (
    format_messages as format_messages_util,
)
from domains.agent.infrastructure.llm.prompt_cache import get_prompt_cache_manager
from domains.agent.infrastructure.llm.providers import get_provider
from domains.gateway.application.bridge_attribution import resolve_gateway_bridge_attribution
from domains.gateway.application.gateway_proxy_factory import get_gateway_proxy
from domains.gateway.application.internal_bridge_actor import resolve_internal_gateway_user_id
from domains.gateway.application.litellm_bridge_payload import (
    split_chat_completion_for_bridge,
    split_embedding_for_bridge,
)
from domains.gateway.application.ports import (
    GatewayCallContext,
    GatewayResponse,
    GatewayStreamChunk,
)
from libs.config.interfaces import LLMConfigProtocol
from utils.logging import get_logger

if TYPE_CHECKING:
    from domains.agent.application.ports.model_catalog_port import ModelCatalogPort
    from domains.gateway.application.ports import GatewayProxyProtocol

logger = get_logger(__name__)


class LLMResponse(BaseModel):
    """LLM 响应"""

    content: str | None = None
    reasoning_content: str | None = None  # 推理模型的思考过程（DeepSeek Reasoner 等）
    tool_calls: list[ToolCall] | None = None
    finish_reason: str | None = None
    usage: dict[str, int] | None = None
    model: str | None = None


class StreamChunk(BaseModel):
    """流式响应块"""

    content: str | None = None
    reasoning_content: str | None = None  # 推理模型的思考过程
    tool_calls: list[dict[str, Any]] | None = None
    finish_reason: str | None = None
    usage: dict[str, int] | None = None


class LLMGateway:
    """
    LLM 网关

    统一多模型接口，支持:
    - 同步/异步调用
    - 流式/非流式响应
    - 工具调用
    - 重试与 Fallback
    """

    def __init__(
        self,
        config: LLMConfigProtocol,
        gateway_proxy: "GatewayProxyProtocol | None" = None,
        model_catalog: "ModelCatalogPort | None" = None,
    ) -> None:
        """
        初始化 LLM Gateway

        Args:
            config: LLM 配置（通过依赖注入传入，避免依赖应用层）
            gateway_proxy: 可选；默认使用 ``get_gateway_proxy()`` 进程内桥接
        """
        self.config = config
        self._gateway_proxy = gateway_proxy or get_gateway_proxy()
        self._model_catalog = model_catalog
        # 初始化 Prompt Cache 管理器
        self._cache_manager = get_prompt_cache_manager()

        # 配置 LiteLLM - 禁用回调以避免不必要的日志记录（litellm 部分符号未导出，用 Any 收窄）
        litellm_any: Any = litellm
        litellm_any.success_callback = []
        litellm_any.failure_callback = []
        litellm_any.set_verbose = False

        # 禁用 LiteLLM 的日志工作线程，避免在程序退出时出现 "I/O operation on closed file" 错误
        # 这会在 atexit 时尝试写入已关闭的日志流
        try:
            # 设置环境变量禁用日志工作线程
            if "LITELLM_LOG" not in os.environ:
                os.environ["LITELLM_LOG"] = "None"
            # 如果日志工作线程已启动，尝试关闭它
            if hasattr(litellm_any, "logging_worker") and litellm_any.logging_worker is not None:
                try:
                    # 停止日志工作线程
                    if hasattr(litellm_any.logging_worker, "stop"):
                        litellm_any.logging_worker.stop()
                except Exception:
                    pass  # 忽略关闭时的错误
        except Exception:
            pass  # 如果无法禁用，继续运行（不影响功能）

        # 在开发环境下启用调试模式，获取详细的错误信息
        if self._should_enable_debug(config):
            _turn_on = getattr(litellm_any, "_turn_on_debug", None)
            if callable(_turn_on):
                _turn_on()
            logger.info("LiteLLM 调试模式已启用 - 将显示详细的请求/响应和错误信息")

        # 设置默认 API Key（仅用于 Anthropic，其他提供商通过 kwargs 传递）
        if config.anthropic_api_key:
            litellm_any.api_key = config.anthropic_api_key.get_secret_value()

    def _should_enable_debug(self, config: LLMConfigProtocol) -> bool:
        """
        检查是否应该启用调试模式

        Args:
            config: LLM 配置对象（应实现 LLMConfigProtocol）

        Returns:
            如果应该启用调试模式则返回 True
        """
        return config.is_development or config.debug

    def _normalize_model_name(self, model: str) -> str:
        """
        规范化模型名称，转换为 litellm 需要的格式

        litellm 对于某些提供商需要使用 provider/model 格式
        复用 get_provider 逻辑保持一致性

        注意：
        - 智谱AI (zhipuai) 需要使用 zai/ 前缀（LiteLLM 要求）
        - 火山引擎需要使用 volcengine/<endpoint_id> 格式
        - 其他提供商（dashscope, deepseek）需要 provider/model 格式
        """
        # 如果已经是 provider/model 格式，直接返回
        if "/" in model:
            return model

        # 根据提供商确定是否需要前缀
        provider = get_provider(model)

        # 智谱AI需要使用 zai/ 前缀（LiteLLM 要求）
        if provider.name == "zhipuai":
            return f"zai/{model}"

        # 火山引擎需要使用 endpoint_id，而不是模型名称
        # 实际的 endpoint_id 会在 chat 方法中通过 _get_api_key 获取并设置
        # 这里先返回一个占位符，实际会在 chat 方法中替换
        if provider.name == "volcengine":
            return f"volcengine/{model}"

        # 需要 provider/model 格式的提供商
        providers_need_prefix = {"dashscope", "deepseek"}

        if provider.name in providers_need_prefix:
            return f"{provider.name}/{model}"

        # Anthropic 和 OpenAI 不需要前缀
        return model

    def _validate_max_tokens(self, model: str, max_tokens: int) -> int:
        """
        验证并限制 max_tokens 根据模型提供商

        Args:
            model: 规范化后的模型名称（可能包含 provider/ 前缀）
            max_tokens: 请求的 max_tokens 值

        Returns:
            调整后的 max_tokens 值
        """
        # 提取提供商名称
        if "/" in model:
            provider = model.split("/")[0]
        else:
            provider_obj = get_provider(model)
            provider = provider_obj.name

        # 不同提供商的最大 token 限制
        max_limits = {
            "deepseek": 65536,  # DeepSeek 最大 65536
            "dashscope": 8192,  # 阿里云通义千问通常最大 8192
            "zhipuai": 8192,  # 智谱AI 通常最大 8192
            "volcengine": 8192,  # 火山引擎通常最大 8192
            "openai": 4096,  # OpenAI GPT-3.5/GPT-4 通常最大 4096（某些模型支持更多）
            "anthropic": 4096,  # Claude 通常最大 4096（某些模型支持更多）
        }

        # 获取该提供商的最大限制
        limit = max_limits.get(provider, 4096)  # 默认 4096

        # 如果超出限制，调整并记录警告
        if max_tokens > limit:
            logger.warning(
                "max_tokens %d 超出 %s 提供商的最大限制 %d，已自动调整为 %d",
                max_tokens,
                provider,
                limit,
                limit,
            )
            return limit

        # 确保至少为 1
        if max_tokens < 1:
            logger.warning("max_tokens %d 小于 1，已自动调整为 1", max_tokens)
            return 1

        return max_tokens

    def _preprocess_messages(
        self, model: str, messages: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        预处理消息，处理模型特定的格式要求

        Args:
            model: 规范化后的模型名称
            messages: 原始消息列表

        Returns:
            处理后的消息列表
        """
        # DeepSeek Reasoner 特殊处理：当 assistant 消息包含工具调用时，需要 reasoning_content 字段
        if self._is_deepseek_reasoner(model):
            processed = []
            for msg in messages:
                msg_copy = msg.copy()
                # 如果是 assistant 消息且包含工具调用，确保有 reasoning_content 字段
                if (
                    msg_copy.get("role") == "assistant"
                    and "tool_calls" in msg_copy
                    and msg_copy["tool_calls"]
                    and "reasoning_content" not in msg_copy
                ):
                    # 如果已有 content，使用它作为 reasoning_content；否则使用空字符串
                    msg_copy["reasoning_content"] = msg_copy.get("content", "") or ""
                processed.append(msg_copy)
            return processed
        return messages

    def _is_deepseek_reasoner(self, model: str) -> bool:
        """判断模型是否为 DeepSeek Reasoner"""
        model_lower = model.lower()
        return "deepseek-reasoner" in model_lower or (
            "deepseek" in model_lower and "reasoner" in model_lower
        )

    def _resolve_model_info(self, model: str, normalized_model: str) -> Any:
        """根据模型名称解析 ModelInfo，用于参数适配。未知模型返回 None。"""
        models_config = get_app_config().models
        info = models_config.get_model(model)
        if info:
            return info
        if normalized_model != model:
            return models_config.get_model(normalized_model)
        return None

    def _adapt_params(self, model_info: Any, kwargs: dict[str, Any]) -> dict[str, Any]:
        """根据模型能力适配请求参数，跳过模型不支持的参数。返回适配后的 kwargs。"""
        if not model_info:
            return kwargs

        adapted = dict(kwargs)

        # 推理模型：不支持 response_format，temperature 固定
        if getattr(model_info, "supports_reasoning", False):
            if adapted.pop("response_format", None):
                logger.warning(
                    "模型 %s 为推理模型，已跳过 response_format",
                    getattr(model_info, "id", "unknown"),
                )
            adapted["temperature"] = 1.0
        # 不支持 json_mode：移除 response_format
        elif not getattr(model_info, "supports_json_mode", True):
            if adapted.pop("response_format", None):
                logger.warning(
                    "模型 %s 不支持 json_mode，已跳过 response_format",
                    getattr(model_info, "id", "unknown"),
                )

        # 不支持工具调用：移除 tools
        if not getattr(model_info, "supports_tools", True):
            adapted.pop("tools", None)
            adapted.pop("tool_choice", None)

        return adapted

    def _compose_chat_completion_kwargs(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str,
        temperature: float,
        max_tokens: int,
        tools: list[dict[str, Any]] | None,
        tool_choice: str | dict | None,
        stream: bool,
        api_key: str | None,
        api_base: str | None,
        response_format: dict[str, Any] | None,
        precomputed_model_info: Any | None = None,
    ) -> dict[str, Any]:
        """构建与直连 LiteLLM 完全一致的 acompletion 参数（桥接与直连共用）。"""
        if api_key:
            api_config: dict[str, Any] = {"api_key": api_key}
            if api_base:
                api_config["api_base"] = api_base
        else:
            api_config = self._get_api_key(model)

        if "endpoint_id" in api_config:
            normalized_model = f"volcengine/{api_config['endpoint_id']}"
        else:
            normalized_model = self._normalize_model_name(model)

        max_tokens_adj = self._validate_max_tokens(normalized_model, max_tokens)
        processed_messages = self._preprocess_messages(normalized_model, messages)
        cached_messages = self._cache_manager.prepare_cacheable_messages(processed_messages, model)

        kwargs: dict[str, Any] = {
            "model": normalized_model,
            "messages": cached_messages,
            "temperature": temperature,
            "max_tokens": max_tokens_adj,
            "stream": stream,
        }

        if self._cache_manager.is_cache_supported(model):
            provider = self._cache_manager.get_provider_from_model(model)
            if provider == "anthropic":
                kwargs["extra_headers"] = {"anthropic-beta": "prompt-caching-2024-07-31"}

        if tools:
            kwargs["tools"] = tools
            if tool_choice:
                kwargs["tool_choice"] = tool_choice

        if response_format:
            kwargs["response_format"] = response_format

        if precomputed_model_info is not None:
            model_info = precomputed_model_info
        else:
            model_info = self._resolve_model_info(model, normalized_model)
        kwargs = self._adapt_params(model_info, kwargs)
        kwargs.update(api_config)
        return kwargs

    async def _compose_chat_completion_kwargs_async(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str,
        temperature: float,
        max_tokens: int,
        tools: list[dict[str, Any]] | None,
        tool_choice: str | dict | None,
        stream: bool,
        api_key: str | None,
        api_base: str | None,
        response_format: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """构建 kwargs；能力元数据优先从 Gateway catalog（异步）解析。"""
        precomputed: Any | None = None
        if self._model_catalog is not None:
            if api_key:
                api_cfg: dict[str, Any] = {"api_key": api_key}
                if api_base:
                    api_cfg["api_base"] = api_base
            else:
                api_cfg = self._get_api_key(model)
            if "endpoint_id" in api_cfg:
                normalized = f"volcengine/{api_cfg['endpoint_id']}"
            else:
                normalized = self._normalize_model_name(model)
            precomputed = await self._model_catalog.resolve_capabilities(model)
            if precomputed is None and normalized != model:
                precomputed = await self._model_catalog.resolve_capabilities(normalized)
        return self._compose_chat_completion_kwargs(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            tool_choice=tool_choice,
            stream=stream,
            api_key=api_key,
            api_base=api_base,
            response_format=response_format,
            precomputed_model_info=precomputed,
        )

    async def chat(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict | None = None,
        stream: bool = False,
        api_key: str | None = None,
        api_base: str | None = None,
        response_format: dict[str, Any] | None = None,
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
            api_key: 可选，覆盖系统 API Key（用户自定义模型）
            api_base: 可选，覆盖系统 API 端点（用户自定义模型）
            response_format: 可选，输出格式约束，如 {"type": "json_object"}

        Returns:
            LLMResponse 或流式生成器
        """
        model = model or self.config.default_model
        litellm_kwargs = await self._compose_chat_completion_kwargs_async(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            tool_choice=tool_choice,
            stream=stream,
            api_key=api_key,
            api_base=api_base,
            response_format=response_format,
        )

        bridge_uid = resolve_internal_gateway_user_id()
        if _global_settings.gateway_internal_proxy_enabled and bridge_uid:
            bridged = await self._maybe_call_via_gateway_litellm(
                litellm_kwargs=litellm_kwargs,
            )
            if bridged is not None:
                return bridged

        if litellm_kwargs["stream"]:
            return self._stream_chat(**litellm_kwargs)
        return await self._chat(**litellm_kwargs)

    def _extract_primitive_value(self, value: Any) -> Any:
        """
        递归提取基本类型值，完全隔离 LiteLLM 对象

        这是核心方法：通过 JSON 序列化/反序列化确保完全转换为基本类型
        """
        # 基本类型直接返回
        if value is None or isinstance(value, str | int | float | bool):
            return value

        # 容器类型递归处理
        if isinstance(value, dict):
            return {k: self._extract_primitive_value(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._extract_primitive_value(item) for item in value]

        # 对象类型：尝试提取属性并递归处理
        dumped = self._extract_object_attributes(value)
        if dumped is not None:
            return self._extract_primitive_value(dumped)

        # 最后尝试转换为字符串
        return str(value)

    def _extract_object_attributes(self, value: Any) -> dict[str, Any] | None:
        """提取对象的属性，返回字典或 None"""
        try:
            # 先尝试使用 model_dump 或 dict 方法
            if hasattr(value, "model_dump"):
                return value.model_dump()
            if hasattr(value, "dict"):
                return value.dict()
            if hasattr(value, "__dict__"):
                return value.__dict__

            # 最后尝试 JSON 序列化
            dumped_json = json.dumps(value, default=str)
            dumped = json.loads(dumped_json)
            # 如果返回的是字符串，说明序列化失败
            if isinstance(dumped, str):
                return None
            return dumped
        except Exception:
            return None

    def _extract_response_dict(self, response: Any) -> dict[str, Any]:
        """从 LiteLLM 响应对象中提取字典"""
        response_dict: dict[str, Any] = {}
        try:
            # 手动构建字典，直接访问 LiteLLM 对象的属性并转换为基本类型
            if hasattr(response, "choices") and response.choices:
                response_dict["choices"] = self._extract_choices(response.choices)
            # 提取 usage
            if hasattr(response, "usage") and response.usage:
                response_dict["usage"] = self._extract_usage(response.usage)
            if hasattr(response, "model") and response.model:
                response_dict["model"] = str(response.model)
        except Exception as e:
            logger.error("Failed to manually extract response data: %s", e, exc_info=True)
            # 如果手动提取失败，尝试 model_dump 作为备用
            if hasattr(response, "model_dump"):
                with suppress(Exception):
                    response_dict = response.model_dump()
            elif hasattr(response, "dict"):
                with suppress(Exception):
                    response_dict = response.dict()
        return response_dict

    def _extract_choices(self, choices: Any) -> list[dict[str, Any]]:
        """提取 choices 列表"""
        result = []
        for choice in choices:
            choice_dict: dict[str, Any] = {}
            if hasattr(choice, "message"):
                choice_dict["message"] = self._extract_message(choice.message)
            if hasattr(choice, "finish_reason"):
                choice_dict["finish_reason"] = (
                    str(choice.finish_reason) if choice.finish_reason else None
                )
            result.append(choice_dict)
        return result

    def _extract_message(self, msg: Any) -> dict[str, Any]:
        """提取 message 对象"""
        msg_dict: dict[str, Any] = {}
        # 提取 content
        if hasattr(msg, "content"):
            msg_dict["content"] = str(msg.content) if msg.content else None
        # 提取 reasoning_content（DeepSeek Reasoner 等推理模型的思考过程）
        if hasattr(msg, "reasoning_content") and msg.reasoning_content:
            msg_dict["reasoning_content"] = str(msg.reasoning_content)
        # 提取 tool_calls
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            msg_dict["tool_calls"] = self._extract_tool_calls(msg.tool_calls)
        return msg_dict

    def _extract_tool_calls(self, tool_calls: Any) -> list[dict[str, Any]]:
        """提取 tool_calls 列表"""
        result = []
        for tc in tool_calls:
            tc_dict: dict[str, Any] = {}
            if hasattr(tc, "id"):
                tc_dict["id"] = str(tc.id) if tc.id else ""
            if hasattr(tc, "function"):
                tc_dict["function"] = self._extract_function(tc.function)
            result.append(tc_dict)
        return result

    def _extract_function(self, func: Any) -> dict[str, Any]:
        """提取 function 对象"""
        func_dict: dict[str, Any] = {}
        if hasattr(func, "name"):
            func_dict["name"] = str(func.name) if func.name else ""
        if hasattr(func, "arguments"):
            func_dict["arguments"] = str(func.arguments) if func.arguments else ""
        return func_dict

    def _extract_usage(self, usage: Any) -> dict[str, int]:
        """提取 usage 对象"""
        return {
            "prompt_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
            "completion_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
            "total_tokens": int(getattr(usage, "total_tokens", 0) or 0),
        }

    def _parse_response_data(self, response_dict: dict[str, Any]) -> LLMResponse:
        """从响应字典中解析 LLMResponse"""
        # 确保是字典并递归提取
        response_dict = self._extract_primitive_value(response_dict)
        if not isinstance(response_dict, dict):
            logger.error("response_dict is not a dict, type: %s", type(response_dict))
            return LLMResponse(content=None, tool_calls=None, finish_reason=None, usage=None)

        # 从纯数据中提取信息
        choices = response_dict.get("choices", [])
        if not choices:
            return LLMResponse(content=None, tool_calls=None, finish_reason=None, usage=None)

        choice = choices[0] if isinstance(choices, list) else {}
        message = choice.get("message", {}) if isinstance(choice, dict) else {}

        # 提取 content
        content = message.get("content") if isinstance(message, dict) else None

        # 提取 reasoning_content（推理模型的思考过程，独立字段）
        reasoning_content = message.get("reasoning_content") if isinstance(message, dict) else None

        # 解析工具调用
        tool_calls = self._parse_tool_calls_from_dict(message)

        # 提取使用情况
        usage_dict = self._parse_usage_from_dict(response_dict)

        # 返回完全转换的内部类型
        return LLMResponse(
            content=str(content) if content else None,
            reasoning_content=str(reasoning_content) if reasoning_content else None,
            tool_calls=tool_calls,
            finish_reason=str(choice.get("finish_reason"))
            if isinstance(choice, dict) and choice.get("finish_reason")
            else None,
            usage=usage_dict,
            model=str(response_dict.get("model")) if response_dict.get("model") else None,
        )

    def _parse_tool_calls_from_dict(self, message: dict[str, Any]) -> list[ToolCall] | None:
        """从消息字典中解析工具调用"""
        if not isinstance(message, dict):
            return None
        message_tool_calls = message.get("tool_calls", [])
        if not message_tool_calls or not isinstance(message_tool_calls, list):
            return None
        tool_calls = []
        for tc in message_tool_calls:
            if isinstance(tc, dict):
                tc_func = tc.get("function", {})
                if isinstance(tc_func, dict):
                    tool_calls.append(
                        ToolCall(
                            id=str(tc.get("id", "")),
                            name=str(tc_func.get("name", "")),
                            arguments=self._parse_arguments(tc_func.get("arguments", "")),
                        )
                    )
        return tool_calls if tool_calls else None

    def _parse_usage_from_dict(self, response_dict: dict[str, Any]) -> dict[str, int] | None:
        """从响应字典中解析使用情况"""
        usage = response_dict.get("usage")
        if not usage or not isinstance(usage, dict):
            return None
        return {
            "prompt_tokens": int(usage.get("prompt_tokens", 0)),
            "completion_tokens": int(usage.get("completion_tokens", 0)),
            "total_tokens": int(usage.get("total_tokens", 0)),
        }

    def _llm_response_from_gateway_chat(self, result: GatewayResponse, model_fallback: str) -> LLMResponse:
        """将桥接层 ``GatewayResponse`` 转为领域 ``LLMResponse``。"""
        tool_calls_raw = result.tool_calls
        tool_calls: list[ToolCall] | None = None
        if tool_calls_raw:
            parsed: list[ToolCall] = []
            for tc in tool_calls_raw:
                if not isinstance(tc, dict):
                    continue
                parsed.append(
                    ToolCall(
                        id=str(tc.get("id", "")),
                        name=str(tc.get("function", {}).get("name", ""))
                        if isinstance(tc.get("function"), dict)
                        else str(tc.get("name", "")),
                        arguments=self._parse_arguments(
                            str(tc.get("function", {}).get("arguments", ""))
                            if isinstance(tc.get("function"), dict)
                            else str(tc.get("arguments", ""))
                        ),
                    )
                )
            tool_calls = parsed or None
        return LLMResponse(
            content=result.content,
            reasoning_content=result.reasoning_content,
            tool_calls=tool_calls,
            finish_reason=result.finish_reason,
            usage=result.usage,
            model=result.model or model_fallback,
        )

    async def _maybe_call_via_gateway_litellm(
        self,
        *,
        litellm_kwargs: dict[str, Any],
    ) -> LLMResponse | AsyncGenerator[StreamChunk, None] | None:
        """通过 AI Gateway 桥接执行调用，参数与 ``acompletion`` 一致。失败返回 None（除非 fail_closed）。"""
        payload = split_chat_completion_for_bridge(litellm_kwargs)
        if payload is None:
            return None
        try:
            bridge = self._gateway_proxy
            attr = resolve_gateway_bridge_attribution()
            ctx = GatewayCallContext(
                user_id=attr.actor_user_id,
                team_id=attr.billing_team_id,
                capability="chat",
            )

            if payload.stream:
                stream_iter = await bridge.chat_completion(
                    payload.messages,
                    ctx=ctx,
                    model=payload.model,
                    temperature=payload.temperature,
                    max_tokens=payload.max_tokens,
                    tools=payload.tools,
                    tool_choice=payload.tool_choice,
                    stream=True,
                    response_format=payload.response_format,
                    api_key=payload.api_key,
                    api_base=payload.api_base,
                    **payload.extras,
                )

                async def _wrap() -> AsyncGenerator[StreamChunk, None]:
                    async for chunk in stream_iter:  # type: ignore[union-attr]
                        chunk_obj: GatewayStreamChunk = chunk
                        yield StreamChunk(
                            content=chunk_obj.content,
                            reasoning_content=chunk_obj.reasoning_content,
                            tool_calls=chunk_obj.tool_calls,
                            finish_reason=chunk_obj.finish_reason,
                            usage=chunk_obj.usage,
                        )

                return _wrap()

            result = await bridge.chat_completion(
                payload.messages,
                ctx=ctx,
                model=payload.model,
                temperature=payload.temperature,
                max_tokens=payload.max_tokens,
                tools=payload.tools,
                tool_choice=payload.tool_choice,
                stream=False,
                response_format=payload.response_format,
                api_key=payload.api_key,
                api_base=payload.api_base,
                **payload.extras,
            )
            return self._llm_response_from_gateway_chat(result, payload.model)
        except Exception as exc:  # pragma: no cover
            if _global_settings.gateway_internal_proxy_fail_closed:
                raise
            logger.warning("Gateway bridge call failed, fallback to direct LiteLLM: %s", exc)
            return None

    def _compose_embedding_litellm_kwargs(self, texts: list[str], model: str) -> dict[str, Any]:
        """构建与直连 ``aembedding`` 一致的参数。"""
        api_config = self._get_embedding_api_config(model)
        return {
            "model": model,
            "input": texts,
            **api_config,
        }

    async def _maybe_embed_via_gateway_litellm(
        self,
        *,
        litellm_kwargs: dict[str, Any],
    ) -> list[list[float]] | None:
        """经 Gateway 批量 embedding，参数与 ``aembedding`` 一致。"""
        parsed = split_embedding_for_bridge(litellm_kwargs)
        if parsed is None:
            return None
        try:
            attr = resolve_gateway_bridge_attribution()
            rows = await self._gateway_proxy.embedding(
                parsed.inputs,
                ctx=GatewayCallContext(
                    user_id=attr.actor_user_id,
                    team_id=attr.billing_team_id,
                    capability="embedding",
                ),
                model=parsed.model,
                api_key=parsed.api_key,
                api_base=parsed.api_base,
                **parsed.extras,
            )
            if not rows:
                return None
            if any(r is None for r in rows):
                return None
            return [list(r) for r in rows if r is not None]
        except Exception as exc:  # pragma: no cover
            if _global_settings.gateway_internal_proxy_fail_closed:
                raise
            logger.warning("Gateway bridge embedding failed, fallback to direct LiteLLM: %s", exc)
            return None

    async def _chat(self, **kwargs: Any) -> LLMResponse:
        """非流式调用

        重新设计：使用 JSON 序列化/反序列化确保完全隔离 LiteLLM 对象
        """
        model = kwargs.get("model", self.config.default_model)
        try:
            response = await acompletion(**kwargs)
            response_dict = self._extract_response_dict(response)
            response_dict.setdefault("model", model)

            # 更新 Prompt Cache 统计（如果提供商支持）
            usage = response_dict.get("usage")
            if usage:
                provider = self._cache_manager.get_provider_from_model(model)
                self._cache_manager.update_stats(usage, provider)

            return self._parse_response_data(response_dict)
        except Exception as e:
            error_msg = str(e)
            # 检查是否是模型不存在的错误
            if "Model Not Exist" in error_msg or "model_not_found" in error_msg.lower():
                logger.error(
                    "模型不存在: %s。请检查模型名称是否正确。"
                    "DeepSeek 支持的模型: deepseek-chat, deepseek-coder, deepseek-reasoner",
                    model,
                )
                # 提供更友好的错误信息
                raise ValueError(
                    f"模型 '{model}' 不存在。"
                    f"DeepSeek 支持的模型: deepseek-chat, deepseek-coder, deepseek-reasoner。"
                    f"请检查配置中的 default_model 设置。"
                ) from e
            # 检查是否是 max_tokens 超出限制的错误
            if "Invalid max_tokens" in error_msg or "max_tokens" in error_msg.lower():
                logger.error(
                    "max_tokens 配置错误: %s。模型: %s",
                    error_msg,
                    model,
                )
                raise ValueError(
                    f"max_tokens 配置错误: {error_msg}。"
                    f"请检查配置中的 agent_max_tokens 设置，确保不超过模型提供商的最大限制。"
                ) from e
            logger.error("LLM call failed: %s", e)
            raise

    def _extract_chunk_dict(self, chunk: Any) -> dict[str, Any]:
        """从流式响应块中提取字典"""
        chunk_dict: dict[str, Any] = {}
        # 先尝试使用 model_dump 或 dict 方法
        if hasattr(chunk, "model_dump"):
            with suppress(Exception):
                chunk_dict = chunk.model_dump()
        elif hasattr(chunk, "dict"):
            with suppress(Exception):
                chunk_dict = chunk.dict()
        elif hasattr(chunk, "__dict__"):
            chunk_dict = chunk.__dict__

        # 如果都失败了，尝试手动提取
        if not chunk_dict and hasattr(chunk, "choices"):
            chunk_dict = {"choices": self._extract_stream_choices(chunk.choices)}
        return chunk_dict

    def _extract_stream_choices(self, choices: Any) -> list[dict[str, Any]]:
        """提取流式响应的 choices"""
        result = []
        try:
            for choice in choices:
                choice_dict: dict[str, Any] = {}
                if hasattr(choice, "delta"):
                    choice_dict["delta"] = self._extract_delta(choice.delta)
                if hasattr(choice, "finish_reason"):
                    choice_dict["finish_reason"] = choice.finish_reason
                result.append(choice_dict)
        except Exception as e:
            logger.error("Failed to manually extract chunk data: %s", e)
        return result

    def _extract_delta(self, delta: Any) -> dict[str, Any]:
        """提取 delta 对象"""
        return {
            "content": getattr(delta, "content", None),
            "tool_calls": getattr(delta, "tool_calls", None),
        }

    def _process_stream_chunk(
        self, chunk_dict: dict[str, Any], tool_calls_buffer: dict[int, dict[str, Any]]
    ) -> StreamChunk | None:
        """处理流式响应块并返回 StreamChunk"""
        # 确保是字典并递归提取
        chunk_dict = self._extract_primitive_value(chunk_dict)
        if not isinstance(chunk_dict, dict):
            logger.error("chunk_dict is not a dict, type: %s", type(chunk_dict))
            return None

        # 从纯数据中提取信息
        choices = chunk_dict.get("choices", [])
        if not choices or not isinstance(choices, list):
            return None

        choice = choices[0] if choices else {}
        if not isinstance(choice, dict):
            return None

        delta = choice.get("delta", {})
        if not isinstance(delta, dict):
            delta = {}

        # 提取 content
        content = delta.get("content")

        # 提取 reasoning_content（推理模型的思考过程，独立字段）
        reasoning_content = delta.get("reasoning_content")

        # 处理工具调用
        self._update_tool_calls_buffer(delta, tool_calls_buffer)

        # 检查完成原因
        finish_reason = choice.get("finish_reason")
        finish_reason_str = str(finish_reason) if finish_reason else None

        return StreamChunk(
            content=str(content) if content else None,
            reasoning_content=str(reasoning_content) if reasoning_content else None,
            tool_calls=list(tool_calls_buffer.values()) if tool_calls_buffer else None,
            finish_reason=finish_reason_str,
        )

    def _update_tool_calls_buffer(
        self, delta: dict[str, Any], tool_calls_buffer: dict[int, dict[str, Any]]
    ) -> None:
        """更新工具调用缓冲区"""
        delta_tool_calls = delta.get("tool_calls", [])
        if not delta_tool_calls or not isinstance(delta_tool_calls, list):
            return

        for tc in delta_tool_calls:
            if not isinstance(tc, dict):
                continue
            idx = int(tc.get("index", 0))
            if idx not in tool_calls_buffer:
                tool_calls_buffer[idx] = {
                    "id": str(tc.get("id", "")),
                    "name": "",
                    "arguments": "",
                }

            tc_function = tc.get("function", {})
            if isinstance(tc_function, dict):
                if "name" in tc_function:
                    tool_calls_buffer[idx]["name"] = str(tc_function["name"])
                if "arguments" in tc_function:
                    tool_calls_buffer[idx]["arguments"] += str(tc_function["arguments"])

    async def _stream_chat(self, **kwargs: Any) -> AsyncGenerator[StreamChunk, None]:
        """流式调用

        重新设计：使用 JSON 序列化/反序列化确保完全隔离 LiteLLM 对象
        """
        try:
            response = await acompletion(**kwargs)
            tool_calls_buffer: dict[int, dict[str, Any]] = {}
            # acompletion 流式返回类型在 stubs 中不统一，用 Any 收窄给 async-for
            stream: Any = response
            async for chunk in stream:
                chunk_dict = self._extract_chunk_dict(chunk)
                stream_chunk = self._process_stream_chunk(chunk_dict, tool_calls_buffer)
                if stream_chunk:
                    yield stream_chunk

        except Exception as e:
            logger.error("LLM stream failed: %s", e)
            raise

    def _get_volcengine_config(self, model_lower: str) -> dict[str, Any] | None:
        """获取火山引擎配置"""
        if not (
            ("doubao" in model_lower or "volcengine" in model_lower)
            and self.config.volcengine_api_key
        ):
            return None

        config: dict[str, Any] = {
            "api_key": self.config.volcengine_api_key.get_secret_value(),
            "api_base": self.config.volcengine_api_base,
        }
        # 根据模型类型选择合适的 endpoint_id
        endpoint_id = self.config.volcengine_chat_endpoint_id or self.config.volcengine_endpoint_id
        if endpoint_id:
            config["endpoint_id"] = endpoint_id
        return config

    def _get_zhipuai_config(self, model_lower: str) -> dict[str, Any] | None:
        """获取智谱AI配置"""
        if not ("glm" in model_lower and self.config.zhipuai_api_key):
            return None

        config: dict[str, Any] = {
            "api_key": self.config.zhipuai_api_key.get_secret_value(),
        }
        # 注意：GLM-4.7 编码套餐只能在特定编程工具中使用，不能通过API单独调用
        # 如果通过API调用GLM-4.7，需要使用通用端点，并确保账户有API额度（不是编码套餐额度）
        # 如果用户明确配置了Coding端点，则使用（但可能不被支持）
        if "glm-4.7" in model_lower and self.config.zhipuai_coding_api_base:
            logger.warning(
                "使用Coding端点调用GLM-4.7，注意：Coding套餐不能通过API单独调用，"
                "如果失败请使用通用端点并确保账户有API额度"
            )
            config["api_base"] = self.config.zhipuai_coding_api_base
        else:
            config["api_base"] = self.config.zhipuai_api_base
        return config

    def _get_api_key(self, model: str) -> dict[str, Any]:
        """
        获取对应模型的 API Key 和配置

        支持的提供商:
        - Anthropic (Claude): claude-*
        - OpenAI (GPT): gpt-*, o1-*
        - 阿里云 DashScope (通义千问): qwen-*
        - DeepSeek: deepseek-*
        - 火山引擎 (豆包): doubao-*
        - 智谱AI (GLM): GLM-*
        """
        model_lower = model.lower()
        config: dict[str, Any] = {}

        # Anthropic (Claude)
        if "claude" in model_lower:
            if self.config.anthropic_api_key:
                config["api_key"] = self.config.anthropic_api_key.get_secret_value()

        # OpenAI (GPT, o1)
        elif "gpt" in model_lower or model_lower.startswith("o1"):
            if self.config.openai_api_key:
                config["api_key"] = self.config.openai_api_key.get_secret_value()
                config["api_base"] = self.config.openai_api_base

        # 阿里云 DashScope (通义千问 Qwen)
        elif "qwen" in model_lower:
            if self.config.dashscope_api_key:
                config["api_key"] = self.config.dashscope_api_key.get_secret_value()
                config["api_base"] = self.config.dashscope_api_base

        # DeepSeek
        elif "deepseek" in model_lower:
            if self.config.deepseek_api_key:
                config["api_key"] = self.config.deepseek_api_key.get_secret_value()
                config["api_base"] = self.config.deepseek_api_base

        # 火山引擎 (豆包)
        elif volcengine_config := self._get_volcengine_config(model_lower):
            config.update(volcengine_config)

        # 智谱AI (GLM)
        elif zhipuai_config := self._get_zhipuai_config(model_lower):
            config.update(zhipuai_config)

        return config

    def _parse_arguments(self, arguments: str) -> dict[str, Any]:
        """解析工具参数"""
        try:
            return json.loads(arguments)
        except json.JSONDecodeError:
            return {"raw": arguments}

    def format_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        """格式化消息为 LLM API 格式（复用公共函数）"""
        return format_messages_util(messages)

    async def count_tokens(self, text: str, model: str | None = None) -> int:
        """计算 token 数量"""
        model = model or self.config.default_model

        try:
            encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            encoding = tiktoken.get_encoding("cl100k_base")

        return len(encoding.encode(text))

    # =========================================================================
    # Embedding 方法
    # =========================================================================

    async def embed(self, text: str, model: str | None = None) -> list[float]:
        """
        生成文本的嵌入向量

        使用 LiteLLM 统一接口，支持多个提供商的 embedding 模型：
        - OpenAI: text-embedding-3-small, text-embedding-3-large
        - 火山引擎: doubao-embedding-*
        - 其他 LiteLLM 支持的 embedding 模型

        Args:
            text: 要嵌入的文本
            model: 嵌入模型名称，默认使用配置中的 embedding_model

        Returns:
            嵌入向量（浮点数列表）
        """
        model = model or self.config.embedding_model
        litellm_kwargs = self._compose_embedding_litellm_kwargs([text], model)
        bridge_uid = resolve_internal_gateway_user_id()
        if _global_settings.gateway_internal_proxy_enabled and bridge_uid:
            bridged = await self._maybe_embed_via_gateway_litellm(
                litellm_kwargs=litellm_kwargs,
            )
            if bridged is not None and len(bridged) > 0 and bridged[0] is not None:
                return list(bridged[0])

        try:
            response = await aembedding(**litellm_kwargs)
            return response.data[0]["embedding"]
        except Exception as e:
            logger.error("Embedding failed for model %s: %s", model, e)
            raise

    async def embed_batch(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        """
        批量生成文本的嵌入向量

        Args:
            texts: 要嵌入的文本列表
            model: 嵌入模型名称，默认使用配置中的 embedding_model

        Returns:
            嵌入向量列表
        """
        model = model or self.config.embedding_model
        if not texts:
            return []
        litellm_kwargs = self._compose_embedding_litellm_kwargs(texts, model)
        bridge_uid = resolve_internal_gateway_user_id()
        if _global_settings.gateway_internal_proxy_enabled and bridge_uid:
            bridged = await self._maybe_embed_via_gateway_litellm(
                litellm_kwargs=litellm_kwargs,
            )
            if bridged is not None and len(bridged) == len(texts):
                return bridged

        try:
            response = await aembedding(**litellm_kwargs)
            return [item["embedding"] for item in response.data]
        except Exception as e:
            logger.error("Batch embedding failed for model %s: %s", model, e)
            raise

    def _get_embedding_api_config(self, model: str) -> dict[str, Any]:
        """
        获取 embedding 模型的 API 配置

        根据模型名称确定提供商，返回对应的 API key 和 base URL

        Args:
            model: 模型名称

        Returns:
            API 配置字典
        """
        model_lower = model.lower()
        config: dict[str, Any] = {}

        # OpenAI embedding 模型
        if "text-embedding" in model_lower or "ada" in model_lower:
            if self.config.openai_api_key:
                config["api_key"] = self.config.openai_api_key.get_secret_value()
                config["api_base"] = self.config.openai_api_base

        # 火山引擎 embedding 模型 (doubao-embedding-*)
        elif "doubao-embedding" in model_lower or "volcengine" in model_lower:
            if self.config.volcengine_api_key:
                config["api_key"] = self.config.volcengine_api_key.get_secret_value()
                config["api_base"] = self.config.volcengine_api_base

        # 阿里云 DashScope embedding 模型
        elif "text-embedding-v" in model_lower or "dashscope" in model_lower:
            if self.config.dashscope_api_key:
                config["api_key"] = self.config.dashscope_api_key.get_secret_value()
                config["api_base"] = self.config.dashscope_api_base

        # 智谱 AI embedding 模型
        elif "embedding" in model_lower and "zhipu" in model_lower:
            if self.config.zhipuai_api_key:
                config["api_key"] = self.config.zhipuai_api_key.get_secret_value()
                config["api_base"] = self.config.zhipuai_api_base

        # 默认使用 OpenAI 配置（兼容大多数 embedding 模型）
        else:
            if self.config.openai_api_key:
                config["api_key"] = self.config.openai_api_key.get_secret_value()
                config["api_base"] = self.config.openai_api_base

        return config
