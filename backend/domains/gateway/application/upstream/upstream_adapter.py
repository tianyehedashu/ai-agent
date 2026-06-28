"""上游协议 quirks：在 Proxy 出站前统一适配 LiteLLM kwargs（编排层，规则在 domain）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from domains.gateway.domain.catalog.model_capability import (
    ModelCapabilitySnapshot,
    tags_to_capability_snapshot,
)
from domains.gateway.domain.provider.moonshot_message_sanitize import (
    is_moonshot_provider,
    sanitize_messages_for_moonshot,
)
from domains.gateway.domain.provider.volcengine_message_sanitize import (
    is_volcengine_provider,
    sanitize_messages_for_volcengine,
)
from domains.gateway.domain.proxy.coding_agent_ua import apply_coding_agent_ua_litellm_params
from domains.gateway.domain.proxy.invocation_policy import apply_invocation_kwargs
from domains.gateway.domain.route.route_capability import route_capability_snapshot
from domains.gateway.domain.upstream.upstream_policy import (
    clamp_max_tokens,
    flatten_text_only_content_arrays,
    max_output_tokens_limit,
    preprocess_messages_for_reasoner,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from domains.gateway.application.catalog.model_or_route_resolution import ResolvedModelName


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
        snap = _resolve_effective_snapshot(resolved, credential_profile_id=credential_profile_id)
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


def _resolve_effective_snapshot(
    resolved: ResolvedModelName,
    *,
    credential_profile_id: str | None,
) -> ModelCapabilitySnapshot:
    """解析用于 ``apply_invocation_kwargs`` 的能力快照。

    路由场景（``primary_records`` 非空）：取所有 primary 能力交集，保证 Router 调度到
    任一 deployment 时出站 kwargs 均合规。单模型场景：取 ``record`` 自身能力。

    注：``credential_profile_id`` 来自调用上下文（vkey 绑定凭据），路由内各 primary 可能
    各自绑定不同 profile；此处用同一 profile_id 构建各 primary 快照属已知近似——影响仅限
    ``temperature_policy`` 的 profile-driven 推导，路由通常同质化 profile，可接受。
    """
    primary_records = resolved.primary_records
    if primary_records is None or len(primary_records) <= 1:
        record = resolved.record
        tags = record.tags if isinstance(record.tags, dict) else {}
        return tags_to_capability_snapshot(
            tags,
            provider=record.provider,
            real_model=record.real_model,
            credential_profile_id=credential_profile_id,
        )
    snapshots: list[ModelCapabilitySnapshot] = []
    for rec in primary_records:
        rec_tags = rec.tags if isinstance(rec.tags, dict) else {}
        snapshots.append(
            tags_to_capability_snapshot(
                rec_tags,
                provider=rec.provider,
                real_model=rec.real_model,
                credential_profile_id=credential_profile_id,
            )
        )
    aggregated = route_capability_snapshot(snapshots)
    # route_capability_snapshot 对非空输入必返回快照；此处防御性回退
    if aggregated is None:
        record = resolved.record
        tags = record.tags if isinstance(record.tags, dict) else {}
        return tags_to_capability_snapshot(
            tags,
            provider=record.provider,
            real_model=record.real_model,
            credential_profile_id=credential_profile_id,
        )
    return aggregated


__all__ = ["UpstreamAdapter"]
