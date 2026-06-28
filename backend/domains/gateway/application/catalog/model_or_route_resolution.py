"""按客户端 ``model`` 名解析 ``GatewayModel`` 或 ``GatewayRoute``。

调用入口可以是：

- ``GatewayModel.name``  → 单 deployment（命中），返回原行；
- ``GatewayRoute.virtual_model`` → 多 deployment（命中），返回路由主选 ``GatewayModel``。

返回 ``ResolvedModelName`` 由 ProxyUseCase 校验 capability、附加下游单价、归因日志使用。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any
import uuid

from domains.gateway.application.route.route_owner_slug_maps import build_route_owner_slug_context
from domains.gateway.domain.route.route_model_ref import (
    RouteModelRefParsed,
    parse_route_model_ref,
)
from domains.gateway.infrastructure.repositories.gateway_route_repository import (
    GatewayRouteRepository,
)

from .gateway_model_listing import resolve_by_name_visible

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from domains.gateway.infrastructure.models.gateway_model import GatewayModel
    from domains.gateway.infrastructure.models.gateway_route import GatewayRoute
    from domains.gateway.infrastructure.models.system_gateway import (
        SystemGatewayModel,
        SystemGatewayRoute,
    )


@dataclass(frozen=True, slots=True)
class GatewayModelResolveSnapshot:
    """``GatewayModel``/``SystemGatewayModel`` 的缓存安全只读快照。

    解析结果会跨请求短 TTL 缓存，不能保存 SQLAlchemy ORM 实例，否则命中后可能访问
    detached/expired 属性。快照保留代理热路径需要的列名，让下游仍可按 ``record.xxx``
    读取。
    """

    id: uuid.UUID
    tenant_id: uuid.UUID | None
    name: str
    capability: str
    real_model: str
    credential_id: uuid.UUID
    provider: str
    weight: int
    rpm_limit: int | None
    tpm_limit: int | None
    enabled: bool
    tags: dict[str, Any] | None
    upstream_call_shape: str | None
    created_by_user_id: uuid.UUID | None = None
    visibility: str | None = None
    last_test_status: str | None = None
    last_tested_at: datetime | None = None
    last_test_reason: str | None = None


@dataclass(frozen=True, slots=True)
class GatewayRouteResolveSnapshot:
    """``GatewayRoute``/``SystemGatewayRoute`` 的缓存安全只读快照。"""

    id: uuid.UUID
    tenant_id: uuid.UUID | None
    virtual_model: str
    primary_models: list[str]
    fallbacks_general: list[str]
    fallbacks_content_policy: list[str]
    fallbacks_context_window: list[str]
    strategy: str
    retry_policy: dict[str, Any] | None
    enabled: bool
    created_by_user_id: uuid.UUID | None = None


if TYPE_CHECKING:
    ResolvedGatewayModel = GatewayModel | SystemGatewayModel | GatewayModelResolveSnapshot
    ResolvedGatewayRoute = GatewayRoute | SystemGatewayRoute | GatewayRouteResolveSnapshot


@dataclass(frozen=True)
class ResolvedModelName:
    """模型名解析结果。

    Attributes:
        record: 用于 capability / 下游单价基准的 ``GatewayModel`` 行（必有）。
        route: 命中 ``GatewayRoute`` 时存在；表示当前调用走多 deployment 调度。
        via_route: 与 ``route`` 同步；为前端/日志快照预留。
        delegated_grant_team_id: 命中跨团队共享授权（委派）时 = 消费团队 T 的 id。
            非 None 表示 ``record`` 为路由 owner 的模型（owner 凭据上游），但 Router
            deployment 与计费均落在消费团队 T；编码 Router model_name 时用 T + 暴露别名。
        exposed_alias: 委派时消费团队内的暴露别名（= 客户端 model）。
        delegated_grant_id: 命中的 ``gateway_route_team_grants`` 行 id；写入日志
            ``route_snapshot`` 供按 grant 维度审计/聚合。
    """

    record: ResolvedGatewayModel
    route: ResolvedGatewayRoute | None
    via_route: str | None
    delegated_grant_team_id: uuid.UUID | None = None
    exposed_alias: str | None = None
    delegated_grant_id: uuid.UUID | None = None


def _uuid_or_none(value: object) -> uuid.UUID | None:
    return value if isinstance(value, uuid.UUID) else None


def _list_copy(value: object) -> list[str]:
    if isinstance(value, list | tuple):
        return [str(item) for item in value]
    return []


def _json_copy(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_copy(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_copy(item) for item in value]
    return value


def _dict_copy(value: object) -> dict[str, Any] | None:
    if isinstance(value, dict):
        copied = _json_copy(value)
        if isinstance(copied, dict):
            return copied
    return None


def _model_snapshot(row: ResolvedGatewayModel) -> GatewayModelResolveSnapshot:
    if isinstance(row, GatewayModelResolveSnapshot):
        return row
    return GatewayModelResolveSnapshot(
        id=row.id,
        tenant_id=_uuid_or_none(getattr(row, "tenant_id", None)),
        name=row.name,
        capability=row.capability,
        real_model=row.real_model,
        credential_id=row.credential_id,
        provider=row.provider,
        weight=row.weight,
        rpm_limit=row.rpm_limit,
        tpm_limit=row.tpm_limit,
        enabled=row.enabled,
        tags=_dict_copy(row.tags),
        upstream_call_shape=row.upstream_call_shape,
        created_by_user_id=_uuid_or_none(getattr(row, "created_by_user_id", None)),
        visibility=getattr(row, "visibility", None),
        last_test_status=getattr(row, "last_test_status", None),
        last_tested_at=getattr(row, "last_tested_at", None),
        last_test_reason=getattr(row, "last_test_reason", None),
    )


def _route_snapshot(row: ResolvedGatewayRoute) -> GatewayRouteResolveSnapshot:
    if isinstance(row, GatewayRouteResolveSnapshot):
        return row
    return GatewayRouteResolveSnapshot(
        id=row.id,
        tenant_id=_uuid_or_none(getattr(row, "tenant_id", None)),
        virtual_model=row.virtual_model,
        primary_models=_list_copy(row.primary_models),
        fallbacks_general=_list_copy(row.fallbacks_general),
        fallbacks_content_policy=_list_copy(row.fallbacks_content_policy),
        fallbacks_context_window=_list_copy(row.fallbacks_context_window),
        strategy=row.strategy,
        retry_policy=_dict_copy(row.retry_policy),
        enabled=row.enabled,
        created_by_user_id=_uuid_or_none(getattr(row, "created_by_user_id", None)),
    )


def cache_safe_resolved_model_name(
    resolved: ResolvedModelName | None,
) -> ResolvedModelName | None:
    """将解析结果转换为可跨 Session 缓存的纯值对象。"""
    if resolved is None:
        return None
    return ResolvedModelName(
        record=_model_snapshot(resolved.record),
        route=_route_snapshot(resolved.route) if resolved.route is not None else None,
        via_route=resolved.via_route,
        delegated_grant_team_id=resolved.delegated_grant_team_id,
        exposed_alias=resolved.exposed_alias,
        delegated_grant_id=resolved.delegated_grant_id,
    )


async def _resolve_personal_team_model(
    session: AsyncSession,
    current_team_id: uuid.UUID,
    name: str,
    *,
    user_id: uuid.UUID,
) -> GatewayModel | SystemGatewayModel | None:
    """共享团队 vkey 下调用个人团队 ``gateway_models`` 注册别名。"""
    from domains.tenancy.application.team_service import TeamService

    personal = await TeamService(session).ensure_personal_team(user_id)
    if personal.id == current_team_id:
        return None
    return await resolve_by_name_visible(session, personal.id, name, user_id=user_id)


async def _resolve_route_primary_record(
    session: AsyncSession,
    route_owner_team_id: uuid.UUID,
    primary_ref: str,
    *,
    user_id: uuid.UUID | None,
) -> GatewayModel | SystemGatewayModel | None:
    ctx = await build_route_owner_slug_context(session, route_owner_team_id)
    cleaned = primary_ref.strip()
    if ctx.enable_slug_prefix:
        parsed = parse_route_model_ref(
            route_owner_tenant_id=route_owner_team_id,
            ref=cleaned,
            slug_to_tenant=ctx.slug_to_tenant,
        )
    else:
        parsed = RouteModelRefParsed(
            route_ref=cleaned,
            target_tenant_id=route_owner_team_id,
            model_name=cleaned,
            matched_slug=None,
        )
    target_tenant = parsed.target_tenant_id or route_owner_team_id
    return await resolve_by_name_visible(
        session,
        target_tenant,
        parsed.model_name,
        user_id=user_id,
    )


async def _resolve_granted_route(
    session: AsyncSession,
    team_id: uuid.UUID,
    alias: str,
) -> ResolvedModelName | None:
    """委派解析：消费团队 T 内的暴露别名命中跨团队共享授权时，以路由 owner 身份解析底层模型。

    Fail-closed：路由被删/停用、owner 缺失（未回填）、owner 已失去底层模型可见性时返回 ``None``，
    使共享调用随权限实时失效。
    """
    from domains.gateway.infrastructure.repositories.gateway_route_grant_repository import (
        GatewayRouteTeamGrantRepository,
    )

    grant = await GatewayRouteTeamGrantRepository(session).resolve_by_tenant_alias(team_id, alias)
    if grant is None:
        return None
    route = await GatewayRouteRepository(session).get(grant.route_id)
    if route is None or not route.enabled:
        return None
    owner_id = route.created_by_user_id
    if owner_id is None:
        return None
    for primary in route.primary_models or ():
        primary_record = await _resolve_route_primary_record(
            session,
            route.tenant_id,
            primary,
            user_id=owner_id,
        )
        if primary_record is not None:
            return ResolvedModelName(
                record=primary_record,
                route=route,
                via_route=route.virtual_model,
                delegated_grant_team_id=team_id,
                exposed_alias=grant.exposed_alias,
                delegated_grant_id=grant.id,
            )
    return None


async def _resolve_model_or_route_uncached(
    session: AsyncSession,
    team_id: uuid.UUID,
    name: str,
    *,
    user_id: uuid.UUID | None = None,
    enable_personal_fallback: bool = True,
) -> ResolvedModelName | None:
    cleaned = name.strip() if name else ""
    if not cleaned:
        return None

    if user_id is not None and enable_personal_fallback:
        personal_record = await _resolve_personal_team_model(
            session, team_id, cleaned, user_id=user_id
        )
        if personal_record is not None:
            return ResolvedModelName(
                record=personal_record,
                route=None,
                via_route=None,
            )

    record = await resolve_by_name_visible(session, team_id, cleaned, user_id=user_id)
    if record is not None:
        return ResolvedModelName(record=record, route=None, via_route=None)
    route = await GatewayRouteRepository(session).resolve_by_virtual_model(team_id, cleaned)
    if route is None:
        from bootstrap.config import settings

        if settings.gateway_route_sharing_enabled:
            return await _resolve_granted_route(session, team_id, cleaned)
        return None
    for primary in route.primary_models or ():
        primary_record = await _resolve_route_primary_record(
            session,
            team_id,
            primary,
            user_id=user_id,
        )
        if primary_record is not None:
            return ResolvedModelName(
                record=primary_record,
                route=route,
                via_route=route.virtual_model,
            )
    return None


async def resolve_model_or_route(
    session: AsyncSession,
    team_id: uuid.UUID,
    name: str,
    *,
    user_id: uuid.UUID | None = None,
    enable_personal_fallback: bool = True,
) -> ResolvedModelName | None:
    """``GatewayModel.name`` 优先，未命中则按 ``GatewayRoute.virtual_model`` 解析主选模型。

    返回 ``None`` 表示该名字既没有对应注册行也没有路由（presentation 层应继续按原 vkey 白名单
    或 LiteLLM 兜底处理）。
    """
    cleaned = name.strip() if name else ""
    if not cleaned:
        return None

    from bootstrap.config import settings
    from domains.gateway.application.grant.resolve_model_cache import (
        CACHE_MISS,
        _fetch_tenant_version,
        peek_resolve_cache_entry,
        put_resolve_cache_entry,
    )

    if settings.gateway_resolve_model_cache_enabled:
        cached = await peek_resolve_cache_entry(team_id, cleaned, user_id=user_id)
        if cached is not CACHE_MISS:
            return cached  # type: ignore[return-value]

    resolved = await _resolve_model_or_route_uncached(
        session, team_id, cleaned, user_id=user_id,
        enable_personal_fallback=enable_personal_fallback,
    )
    if settings.gateway_resolve_model_cache_enabled:
        # 写入时绑定当前版本号，便于读路径比较；版本拉取失败退化为空串
        # （仍可由 TTL 兜底，与旧版行为一致）
        version = await _fetch_tenant_version(team_id)
        put_resolve_cache_entry(
            team_id, cleaned, user_id=user_id, resolved=resolved, version=version
        )
    return resolved


__all__ = [
    "GatewayModelResolveSnapshot",
    "GatewayRouteResolveSnapshot",
    "ResolvedModelName",
    "cache_safe_resolved_model_name",
    "resolve_model_or_route",
]
