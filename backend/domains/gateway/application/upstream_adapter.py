"""上游协议 quirks：在 Proxy 出站前统一适配 LiteLLM kwargs（编排层，规则在 domain）。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from domains.gateway.domain.model_capability import tags_to_capability_snapshot
from domains.gateway.domain.policies.invocation_policy import apply_invocation_kwargs
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
from domains.gateway.domain.upstream_profile_registry import get_upstream_profile

if TYPE_CHECKING:
    from domains.gateway.application.model_or_route_resolution import ResolvedModelName


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
            return dict(kwargs)
        record = resolved.record
        tags = record.tags if isinstance(record.tags, dict) else {}
        snap = tags_to_capability_snapshot(
            tags,
            provider=record.provider,
            real_model=record.real_model,
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
        if is_volcengine_provider(record.provider):
            volcengine_messages = adapted.get("messages")
            if isinstance(volcengine_messages, list):
                adapted["messages"] = sanitize_messages_for_volcengine(volcengine_messages)
        adapted = self._inject_coding_agent_ua(
            adapted,
            provider=record.provider,
            credential_profile_id=credential_profile_id,
        )
        return adapted

    @staticmethod
    def _inject_coding_agent_ua(
        kwargs: dict[str, Any],
        *,
        provider: str,
        credential_profile_id: str | None,
    ) -> dict[str, Any]:
        """若 profile 声明 ``coding_agent_ua``，注入到 ``extra_headers["user-agent"]``。"""
        profile = get_upstream_profile(credential_profile_id, provider=provider)
        ua = profile.coding_agent_ua
        if not ua:
            return kwargs
        headers = dict(kwargs.get("extra_headers") or {})
        headers["User-Agent"] = ua
        kwargs["extra_headers"] = headers
        return kwargs


__all__ = ["UpstreamAdapter"]
