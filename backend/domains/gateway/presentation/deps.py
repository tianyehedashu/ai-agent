"""
Gateway Presentation Dependencies - 网关认证依赖注入

提供：
- bearer_vkey_auth: Bearer sk-gw-... 认证（用于 /v1/*）
- bearer_vkey_or_apikey_auth: 同时支持 sk-gw- 和带 gateway:proxy scope 的 sk-
- CurrentTeam / RequiredTeamMember / RequiredTeamAdmin / RequiredTeamOwner
- RequiredGatewayAdmin: 平台 admin 或 team admin

注意：
- 匿名用户访问 Gateway 任何接口直接 401
- 团队上下文从 X-Team-Id 头或路径变量解析；缺省取 personal team
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated
import uuid

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from domains.gateway.application.gateway_access_use_case import GatewayAccessUseCase
from domains.gateway.domain.errors import VirtualKeyInvalidError
from domains.gateway.domain.types import VirtualKeyPrincipal
from domains.gateway.domain.virtual_key_service import is_vkey_format
from domains.gateway.presentation.http_error_map import http_exception_from_gateway_domain
from domains.identity.application.api_key_use_case import ApiKeyUseCase
from domains.identity.domain.api_key_types import ApiKeyScope
from domains.tenancy.presentation.team_dependencies import (
    CurrentTeam,
    RequiredGatewayAdmin,
    RequiredTeamAdmin,
    RequiredTeamMember,
    RequiredTeamOwner,
    ResolvedTeam,
    resolve_current_team,
)
from libs.db.database import get_db
from libs.db.permission_context import PermissionContext, set_permission_context
from libs.exceptions import HttpMappableDomainError

__all__ = [
    "CurrentTeam",
    "GatewayPrincipal",
    "RequiredGatewayAdmin",
    "RequiredTeamAdmin",
    "RequiredTeamMember",
    "RequiredTeamOwner",
    "ResolvedTeam",
    "VkeyOrApikeyPrincipal",
    "bearer_vkey_auth",
    "bearer_vkey_or_apikey_auth",
    "resolve_current_team",
]

_security = HTTPBearer(auto_error=True)


# =============================================================================
# /v1/* 鉴权
# =============================================================================


@dataclass(frozen=True)
class GatewayPrincipal:
    """已鉴权的虚拟 Key 主体"""

    vkey: VirtualKeyPrincipal
    team_id: uuid.UUID
    user_id: uuid.UUID | None  # 创建者；system vkey 可能为空


async def bearer_vkey_auth(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_security)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GatewayPrincipal:
    """Bearer sk-gw-... 认证

    1. 校验格式
    2. 哈希查表
    3. 校验是否激活/未过期
    4. 注入 PermissionContext
    """
    plain = credentials.credentials.strip()
    if not is_vkey_format(plain):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid virtual key format",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access = GatewayAccessUseCase(db)
    try:
        record = await access.validate_bearer_virtual_key(plain)
    except VirtualKeyInvalidError as exc:
        raise http_exception_from_gateway_domain(exc) from exc

    await access.record_virtual_key_usage(record.id)

    team_role = await access.team_role_for_virtual_key_creator(
        record.team_id, record.created_by_user_id
    )

    vkey_principal = VirtualKeyPrincipal(
        vkey_id=record.id,
        vkey_name=record.name,
        team_id=record.team_id,
        user_id=record.created_by_user_id,
        allowed_models=tuple(record.allowed_models or ()),
        allowed_capabilities=tuple(record.allowed_capabilities or ()),  # type: ignore[arg-type]
        rpm_limit=record.rpm_limit,
        tpm_limit=record.tpm_limit,
        store_full_messages=record.store_full_messages,
        guardrail_enabled=record.guardrail_enabled,
        is_system=record.is_system,
    )

    set_permission_context(
        PermissionContext(
            user_id=record.created_by_user_id,
            anonymous_user_id=None,
            role="user",
            team_id=record.team_id,
            team_role=team_role,
        )
    )

    return GatewayPrincipal(
        vkey=vkey_principal,
        team_id=record.team_id,
        user_id=record.created_by_user_id,
    )


@dataclass(frozen=True)
class VkeyOrApikeyPrincipal:
    """同时支持 sk-gw-... 和 sk-...（带 gateway:proxy scope）的认证结果"""

    via: str  # "vkey" / "apikey"
    user_id: uuid.UUID | None
    team_id: uuid.UUID
    vkey: VirtualKeyPrincipal | None = None


async def bearer_vkey_or_apikey_auth(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_security)],
    db: Annotated[AsyncSession, Depends(get_db)],
    x_team_id: Annotated[str | None, Header(alias="X-Team-Id")] = None,
) -> VkeyOrApikeyPrincipal:
    """同时支持 sk-gw-... 与 sk- + gateway:proxy scope

    sk- 时使用 X-Team-Id 头指定团队（默认 personal team）。
    """
    plain = credentials.credentials.strip()

    if is_vkey_format(plain):
        gp = await bearer_vkey_auth(credentials=credentials, db=db)
        return VkeyOrApikeyPrincipal(
            via="vkey",
            user_id=gp.user_id,
            team_id=gp.team_id,
            vkey=gp.vkey,
        )

    use_case = ApiKeyUseCase(db)
    entity = await use_case.verify_api_key(plain)
    if entity is None or not entity.is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not entity.can_access(ApiKeyScope.GATEWAY_PROXY):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API key missing scope: gateway:proxy",
        )

    access = GatewayAccessUseCase(db)
    try:
        team, team_role = await access.resolve_team_for_gateway_proxy(
            entity.user_id, x_team_id
        )
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc

    set_permission_context(
        PermissionContext(
            user_id=entity.user_id,
            anonymous_user_id=None,
            role="user",
            team_id=team.id,
            team_role=team_role,
        )
    )

    return VkeyOrApikeyPrincipal(
        via="apikey",
        user_id=entity.user_id,
        team_id=team.id,
    )


# 团队上下文见 ``domains.tenancy.presentation.team_dependencies``（由上方 import 再导出）。
