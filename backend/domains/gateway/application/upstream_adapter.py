"""上游协议 quirks：在 Proxy 出站前统一适配 LiteLLM kwargs（编排层，规则在 domain）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from domains.gateway.domain.coding_agent_ua import apply_coding_agent_ua_litellm_params
from domains.gateway.domain.model_capability import tags_to_capability_snapshot
from domains.gateway.domain.policies.invocation_policy import apply_invocation_kwargs
from domains.gateway.domain.policies.moonshot_message_sanitize import (
    is_moonshot_provider,
    sanitize_messages_for_moonshot,
)
from domains.gateway.domain.policies.volcengine_message_sanitize import (
    is_volcengine_provider,
    sanitize_messages_for_volcengine,
)
from domains.gateway.domain.upstream_policy import (
    clamp_max_tokens,
    flatten_text_only_content_arrays,
    max_output_tokens_limit,
    preprocess_messages_for_reasoner,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from domains.gateway.application.model_or_route_resolution import ResolvedModelName


@dataclass(frozen=True, slots=True)
class _MessageSanitizePolicy:
    """Provider 消息清洗策略注册项。"""

    is_match: Callable[[str | None], bool]
    sanitize: Callable[[list[Any]], list[Any]]


_MESSAGE_SANITIZE_POLICIES: tuple[_MessageSanitizePolicy, ...] = (
    _MessageSanitizePolicy(
        is_match=is_volcengine_provider,
        sanitize=sanitize_messages_for_volcengine,
    ),
    _MessageSanitizePolicy(
        is_match=is_moonshot_provider,
        sanitize=sanitize_messages_for_moonshot,
    ),
)


def _apply_message_sanitize_policy(
    provider: str | None,
    adapted: dict[str, Any],
    policies: tuple[_MessageSanitizePolicy, ...],
) -> None:
    """若 provider 匹配注册策略，则对 ``adapted["messages"]`` 执行对应清洗。"""
    for policy in policies:
        if policy.is_match(provider):
            messages = adapted.get("messages")
            if isinstance(messages, list):
                adapted["messages"] = policy.sanitize(messages)
            return


class UpstreamAdapter:
    """将 OpenAI 形 body 适配为可安全出站的 LiteLLM kwargs。"""

    def adapt(
        self,
        kwargs: dict[str, Any],
        *,
        client_model: str,
        resolved: ResolvedModelName | None,
        credential_profile_id: str | None = None,
    ) -> dict[str, Any]:
        if resolved is None:
            # Fast path：无 resolved 时仅可能注入 coding_agent UA，其余字段不变。
            return self._inject_coding_agent_ua(
                kwargs,
                provider="",
                credential_profile_id=credential_profile_id,
            )
        record = resolved.record
        tags = record.tags if isinstance(record.tags, dict) else {}
        snap = tags_to_capability_snapshot(
            tags,
            provider=record.provider,
            real_model=record.real_model,
            credential_profile_id=credential_profile_id,
        )
        adapted = apply_invocation_kwargs(snap, kwargs)
        limit = max_output_tokens_limit(tags, record.provider)
        adapted = clamp_max_tokens(adapted, limit)
        messages = adapted.get("messages")
        if isinstance(messages, list):
            adapted["messages"] = preprocess_messages_for_reasoner(
                client_model,
                record.real_model,
                messages,
                supports_reasoning=snap.supports_reasoning,
            )
        if not snap.supports_vision:
            messages = adapted.get("messages")
            if isinstance(messages, list):
                adapted["messages"] = flatten_text_only_content_arrays(messages)
        _apply_message_sanitize_policy(record.provider, adapted, _MESSAGE_SANITIZE_POLICIES)
        adapted = self._inject_coding_agent_ua(
            adapted,
            provider=record.provider,
            credential_profile_id=credential_profile_id,
            real_model=record.real_model,
        )
        return adapted

    @staticmethod
    def _inject_coding_agent_ua(
        kwargs: dict[str, Any],
        *,
        provider: str,
        credential_profile_id: str | None,
        real_model: str | None = None,
    ) -> dict[str, Any]:
        """若 profile 声明 ``coding_agent_ua``，注入到 ``extra_headers["User-Agent"]``。"""
        return apply_coding_agent_ua_litellm_params(
            kwargs,
            credential_profile_id=credential_profile_id,
            provider=provider,
            real_model=real_model,
        )


__all__ = ["UpstreamAdapter"]
