"""代理调用 metadata 与 LiteLLM kwargs 构建。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from bootstrap.config import settings
from domains.gateway.application.model_or_route_resolution import resolve_model_or_route
from domains.gateway.application.pricing.pricing_proxy_metadata import (
    apply_downstream_custom_pricing_kwargs,
    attach_downstream_pricing_metadata,
)
from domains.gateway.application.route_snapshot_cache import get_route_snapshot_metadata
from domains.gateway.application.router_model_name import router_model_name_for_client
from domains.gateway.domain.guardrail_policy import effective_guardrail_enabled
from domains.gateway.domain.types import credential_api_scope
from domains.gateway.infrastructure.repositories.credential_repository import (
    ProviderCredentialRepository,
)
from domains.tenancy.application.team_service import TeamService

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.gateway.application.model_or_route_resolution import ResolvedModelName
    from domains.gateway.application.proxy_use_case import ProxyContext


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
    ) -> dict[str, Any]:
        """按虚拟模型名解析 GatewayModel -> 凭据，供日志归因。"""
        if not virtual_model:
            return {}
        resolved = await resolve_model_or_route(
            self._session, team_id, virtual_model, user_id=user_id
        )
        if resolved is None:
            return {}
        if resolved.route is not None:
            return {
                "gateway_via_route": resolved.via_route,
                "gateway_provider": resolved.record.provider,
            }
        record = resolved.record
        cred = await ProviderCredentialRepository(self._session).get(record.credential_id)
        if cred is None:
            return {}
        return {
            "gateway_credential_id": str(cred.id),
            "gateway_credential_name_snapshot": cred.name,
            "gateway_credential_scope": credential_api_scope(
                scope=cred.scope,
                tenant_id=cred.tenant_id,
            ),
            "gateway_provider": record.provider,
        }

    async def build(
        self,
        ctx: ProxyContext,
        *,
        user_kwargs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """生成单次代理调用的 Gateway metadata。"""
        team = await TeamService(self._session).get_team(ctx.team_id)
        verbose_log = bool(ctx.store_full_messages)
        meta: dict[str, Any] = {
            "gateway_team_id": str(ctx.team_id),
            "gateway_user_id": str(ctx.user_id) if ctx.user_id else None,
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
        if user_kwargs:
            await self._merge_user_and_model_metadata(ctx, meta, user_kwargs)
        return meta

    async def prepare_litellm_kwargs(
        self,
        ctx: ProxyContext,
        body: dict[str, Any],
    ) -> PreparedLitellmKwargs:
        """拼装 metadata，并把下游单价注入 LiteLLM kwargs。"""
        metadata = await self.build(ctx, user_kwargs=body)
        kwargs = dict(body)
        kwargs["metadata"] = metadata
        apply_downstream_custom_pricing_kwargs(kwargs)
        raw_model = kwargs.get("model")
        client_model = str(raw_model).strip() if raw_model is not None else ""
        resolved = None
        if client_model:
            resolved = await resolve_model_or_route(
                self._session, ctx.team_id, client_model, user_id=ctx.user_id
            )
            kwargs["model"] = router_model_name_for_client(ctx.team_id, client_model, resolved)
        return PreparedLitellmKwargs(
            kwargs=kwargs,
            client_model=client_model,
            resolved=resolved,
        )

    async def _merge_user_and_model_metadata(
        self,
        ctx: ProxyContext,
        meta: dict[str, Any],
        user_kwargs: dict[str, Any],
    ) -> None:
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
            return
        meta.update(
            await self.credential_metadata_for_virtual_model(
                ctx.team_id, virtual_model, user_id=ctx.user_id
            )
        )
        snap = await get_route_snapshot_metadata(self._session, ctx.team_id, virtual_model)
        if snap is not None:
            meta["gateway_route_snapshot"] = snap
        billing_package = "entitlement" if ctx.entitlement_state is not None else None
        await attach_downstream_pricing_metadata(
            self._session,
            meta,
            team_id=ctx.team_id,
            virtual_model=virtual_model,
            entitlement_plan_id=(
                ctx.entitlement_state.plan_id if ctx.entitlement_state is not None else None
            ),
            billing_package=billing_package,
        )


__all__ = ["PreparedLitellmKwargs", "ProxyMetadataBuilder"]
