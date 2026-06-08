"""代理调用 metadata 与 LiteLLM kwargs 构建。"""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import TYPE_CHECKING, Any
import uuid

from bootstrap.config import settings
from domains.gateway.application.model_or_route_resolution import (
    ResolvedModelName,
)
from domains.gateway.application.pricing.pricing_proxy_metadata import (
    apply_downstream_custom_pricing_kwargs,
    attach_downstream_pricing_metadata,
)
from domains.gateway.application.proxy_router_team_metadata import (
    ensure_litellm_router_team_metadata,
)
from domains.gateway.application.proxy_timing import ProxyPrepareTimings
from domains.gateway.application.route_snapshot_cache import get_route_snapshot_metadata
from domains.gateway.application.router_model_name import router_model_name_for_client
from domains.gateway.domain.guardrail_policy import effective_guardrail_enabled
from domains.gateway.domain.types import credential_api_scope
from domains.gateway.infrastructure.repositories.credential_repository import (
    ProviderCredentialRepository,
)
from domains.tenancy.application.team_service import TeamService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.gateway.application.proxy_context import ProxyContext


def _uuid_from_metadata_value(value: object) -> uuid.UUID | None:
    if value is None:
        return None
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True, slots=True)
class PreparedLitellmKwargs:
    """单次出站 LiteLLM 调用的 kwargs 与已解析路由（避免重复 resolve）。"""

    kwargs: dict[str, Any]
    client_model: str
    resolved: ResolvedModelName | None


class ProxyMetadataBuilder:
    """构建 Gateway 日志、归因、定价与 Router 所需的调用 metadata。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def credential_metadata_for_virtual_model(
        self,
        team_id: uuid.UUID,
        virtual_model: str | None,
        *,
        user_id: uuid.UUID | None = None,
        resolved: ResolvedModelName | None = None,
    ) -> dict[str, Any]:
        """按虚拟模型名解析 GatewayModel -> 凭据，供日志归因。"""
        if not virtual_model:
            return {}
        model_resolved = resolved
        if model_resolved is None:
            from domains.gateway.application.model_or_route_resolution import (
                resolve_model_or_route,
            )

            model_resolved = await resolve_model_or_route(
                self._session, team_id, virtual_model, user_id=user_id
            )
        if model_resolved is None:
            return {}
        if model_resolved.route is not None:
            return {
                "gateway_via_route": model_resolved.via_route,
                "gateway_provider": model_resolved.record.provider,
            }
        record = model_resolved.record
        cred_id = record.credential_id
        if cred_id is None:
            return {"gateway_provider": record.provider}
        cred = await ProviderCredentialRepository(self._session).get(cred_id)
        if cred is None:
            return {}
        return {
            "gateway_credential_id": str(cred.id),
            "gateway_credential_name_snapshot": cred.name,
            "gateway_credential_scope": credential_api_scope(
                scope=cred.scope,
                tenant_id=cred.tenant_id,
            ),
            "gateway_credential_profile_id": cred.profile_id,
            "gateway_provider": record.provider,
        }

    async def build(
        self,
        ctx: ProxyContext,
        *,
        user_kwargs: dict[str, Any] | None = None,
        resolved: ResolvedModelName | None = None,
        timings: ProxyPrepareTimings | None = None,
    ) -> dict[str, Any]:
        """生成单次代理调用的 Gateway metadata。"""
        meta_started = time.perf_counter()
        team = await TeamService(self._session).get_team(ctx.team_id)
        effective_user_id = ctx.user_id
        if effective_user_id is None and team is not None and team.kind == "personal":
            effective_user_id = team.owner_user_id
        verbose_log = bool(ctx.store_full_messages)
        team_id_str = str(ctx.team_id)
        user_id_str = str(effective_user_id) if effective_user_id else None
        meta: dict[str, Any] = {
            "gateway_team_id": team_id_str,
            # LiteLLM Router async 路径 filter_team_based_models 要求与 model_info.team_id 一致
            "user_api_key_team_id": team_id_str,
            "gateway_user_id": user_id_str,
            # Router ageneric_api_call 回调常剥离顶层 gateway_*；标准键更易保留到 CustomLogger
            "user_api_key_user_id": user_id_str,
            "gateway_vkey_id": str(ctx.vkey.vkey_id) if ctx.vkey else None,
            "gateway_inbound_via": ctx.inbound_via,
            "gateway_platform_api_key_id": (
                str(ctx.platform_api_key_id) if ctx.platform_api_key_id else None
            ),
            "gateway_platform_api_key_grant_id": (
                str(ctx.platform_api_key_grant_id) if ctx.platform_api_key_grant_id else None
            ),
            "gateway_capability": ctx.capability.value,
            "gateway_request_id": ctx.request_id,
            "gateway_team_snapshot": ({"name": team.name, "kind": team.kind} if team else None),
            "gateway_user_email_snapshot": ctx.user_display_snapshot,
            "gateway_vkey_name_snapshot": ctx.vkey.vkey_name if ctx.vkey else None,
            "guardrail_enabled": effective_guardrail_enabled(
                global_guardrail_enabled=settings.gateway_default_guardrail_enabled,
                vkey_guardrail_enabled=ctx.guardrail_enabled,
            ),
            "gateway_entitlement_plan_id": (
                str(ctx.entitlement_state.plan_id) if ctx.entitlement_state is not None else None
            ),
            "gateway_store_full_messages": verbose_log,
            "gateway_log_prompt_max_chars": int(settings.gateway_request_log_prompt_max_chars),
            "gateway_log_response_max_chars": int(
                settings.gateway_request_log_response_verbose_max_chars
                if verbose_log
                else settings.gateway_request_log_response_preview_max_chars
            ),
            "gateway_client_ua": ctx.client_ua,
            "gateway_client_type": ctx.client_type,
        }
        gateway_snapshot = {
            key: value for key, value in meta.items() if str(key).startswith("gateway_")
        }
        if gateway_snapshot:
            # Router anthropic_messages / ageneric_api_call 回调常剥离顶层 gateway_*；
            # LiteLLM 标准键 user_api_key_auth_metadata 更易保留到 CustomLogger。
            meta["user_api_key_auth_metadata"] = gateway_snapshot
        base_meta_ms = int((time.perf_counter() - meta_started) * 1000)
        if user_kwargs:
            merge_timings = await self._merge_user_and_model_metadata(
                ctx,
                meta,
                user_kwargs,
                resolved=resolved,
            )
            if timings is not None:
                timings.metadata_ms = base_meta_ms + merge_timings.metadata_ms
                timings.pricing_ms = merge_timings.pricing_ms
        elif timings is not None:
            timings.metadata_ms = base_meta_ms
        return meta

    async def prepare_litellm_kwargs(
        self,
        ctx: ProxyContext,
        body: dict[str, Any],
        *,
        resolved: ResolvedModelName | None = None,
        timings: ProxyPrepareTimings | None = None,
    ) -> PreparedLitellmKwargs:
        """拼装 metadata，并把下游单价注入 LiteLLM kwargs。"""
        metadata = await self.build(
            ctx,
            user_kwargs=body,
            resolved=resolved,
            timings=timings,
        )
        kwargs = dict(body)
        kwargs["metadata"] = metadata
        ensure_litellm_router_team_metadata(
            kwargs,
            ctx.team_id,
            user_id=_uuid_from_metadata_value(metadata.get("gateway_user_id")),
        )
        apply_downstream_custom_pricing_kwargs(kwargs)
        raw_model = kwargs.get("model")
        client_model = str(raw_model).strip() if raw_model is not None else ""
        model_resolved = resolved
        if client_model and model_resolved is None:
            from domains.gateway.application.model_or_route_resolution import (
                resolve_model_or_route,
            )

            model_resolved = await resolve_model_or_route(
                self._session, ctx.team_id, client_model, user_id=ctx.user_id
            )
        if client_model:
            encoded = router_model_name_for_client(ctx.team_id, client_model, model_resolved)
            kwargs["model"] = encoded
        return PreparedLitellmKwargs(
            kwargs=kwargs,
            client_model=client_model,
            resolved=model_resolved,
        )

    async def _merge_user_and_model_metadata(
        self,
        ctx: ProxyContext,
        meta: dict[str, Any],
        user_kwargs: dict[str, Any],
        *,
        resolved: ResolvedModelName | None = None,
    ) -> _MergeTimings:
        user_meta = user_kwargs.get("metadata") or {}
        if isinstance(user_meta, dict):
            meta.update(
                {
                    k: v
                    for k, v in user_meta.items()
                    if k not in meta and not str(k).startswith("gateway_")
                }
            )
        raw_model = user_kwargs.get("model")
        virtual_model = str(raw_model).strip() if raw_model is not None else None
        if not virtual_model:
            return _MergeTimings()
        # 客户端原始模型别名：供日志 route_name 使用，避免 fallback 到编码后的 Router model_name
        meta["gateway_route_name"] = virtual_model
        cred_started = time.perf_counter()
        meta.update(
            await self.credential_metadata_for_virtual_model(
                ctx.team_id,
                virtual_model,
                user_id=ctx.user_id,
                resolved=resolved,
            )
        )
        snap = await get_route_snapshot_metadata(self._session, ctx.team_id, virtual_model)
        if snap is not None:
            meta["gateway_route_snapshot"] = snap
        metadata_ms = int((time.perf_counter() - cred_started) * 1000)
        billing_package = "entitlement" if ctx.entitlement_state is not None else None
        pricing_started = time.perf_counter()
        await attach_downstream_pricing_metadata(
            self._session,
            meta,
            team_id=ctx.team_id,
            virtual_model=virtual_model,
            entitlement_plan_id=(
                ctx.entitlement_state.plan_id if ctx.entitlement_state is not None else None
            ),
            billing_package=billing_package,
            resolved=resolved,
        )
        pricing_ms = int((time.perf_counter() - pricing_started) * 1000)
        return _MergeTimings(metadata_ms=metadata_ms, pricing_ms=pricing_ms)


@dataclass(slots=True)
class _MergeTimings:
    metadata_ms: int = 0
    pricing_ms: int = 0


__all__ = ["PreparedLitellmKwargs", "ProxyMetadataBuilder"]
