"""上游协议 quirks：在 Proxy 出站前统一适配 LiteLLM kwargs（编排层，规则在 domain）。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from domains.gateway.domain.model_capability import tags_to_capability_snapshot
from domains.gateway.domain.upstream_policy import (
    UpstreamCapabilityFlags,
    adapt_kwargs_by_capability,
    clamp_max_tokens,
    max_output_tokens_limit,
    preprocess_messages_for_reasoner,
)

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
    ) -> dict[str, Any]:
        if resolved is None:
            return dict(kwargs)
        record = resolved.record
        tags = record.tags if isinstance(record.tags, dict) else {}
        snap = tags_to_capability_snapshot(tags)
        flags = UpstreamCapabilityFlags(
            supports_tools=snap.supports_tools,
            supports_reasoning=snap.supports_reasoning,
            supports_json_mode=snap.supports_json_mode,
        )
        adapted = adapt_kwargs_by_capability(kwargs, flags)
        limit = max_output_tokens_limit(tags, record.provider)
        adapted = clamp_max_tokens(adapted, limit)
        messages = adapted.get("messages")
        if isinstance(messages, list):
            adapted["messages"] = preprocess_messages_for_reasoner(
                client_model,
                record.real_model,
                messages,
            )
        return adapted


__all__ = ["UpstreamAdapter"]
