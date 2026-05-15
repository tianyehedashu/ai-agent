"""
Gateway Presentation Dependencies - 网关认证依赖注入

提供：
- bearer_vkey_auth: Bearer sk-gw-... 认证（用于 /v1/*）
- bearer_vkey_or_apikey_auth: 同时支持 sk-gw- 和带 gateway:proxy scope 的 sk-；
  另支持 **x-api-key** 头（与 Anthropic SDK 一致），与 ``Authorization: Bearer`` 二选一，
  二者同时存在时 **优先 Bearer**。
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
from domains.gateway.domain.types import (
    ApiKeyGatewayGrantPrincipal,
    GatewayInboundVia,
    VirtualKeyPrincipal,
    allowed_capabilities_from_storage,
)
from domains.gateway.domain.virtual_key_service import is_vkey_format
from domains.gateway.presentation.http_error_map import http_exception_from_gateway_domain
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
from utils.logging import get_logger

logger = get_logger(__name__)

__all__ = [
    "CurrentTeam",
    "GatewayInboundVia",
    "GatewayPrincipal",
    "RequiredGatewayAdmin",
    "RequiredTeamAdmin",
    "RequiredTeamMember",
    "RequiredTeamOwner",
    "ResolvedTeam",
    "VkeyOrApikeyPrincipal",
    "bearer_vkey_auth",
    "bearer_vkey_or_apikey_auth",
    "pick_gateway_proxy_plain_token",
    "resolve_current_team",
]

_security = HTTPBearer(auto_error=True)
_optional_security = HTTPBearer(auto_error=False)


# =============================================================================
# /v1/* 鉴权
# =============================================================================


def pick_gateway_proxy_plain_token(
    credentials: HTTPAuthorizationCredentials | None,
    x_api_key: str | None,
) -> str:
    """解析 OpenAI/Anthropic 网关代理用的明文 token（sk-gw- 或带 gateway:proxy 的 sk-）。

    优先 ``Authorization: Bearer``；缺省时使用 ``x-api-key``。
    """
    if credentials is not None and credentials.credentials.strip():
        return credentials.credentials.strip()
    if x_api_key is not None and x_api_key.strip():
        return x_api_key.strip()
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def _gateway_principal_from_vkey_plain(
    plain: str,
    db: AsyncSession,
) -> GatewayPrincipal:
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

    try:
        caps = allowed_capabilities_from_storage(record.allowed_capabilities)
    except ValueError:
        logger.exception(
            "virtual key %s has invalid allowed_capabilities in DB",
            record.id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invalid virtual key capability configuration",
        ) from None

    vkey_principal = VirtualKeyPrincipal(
        vkey_id=record.id,
        vkey_name=record.name,
        team_id=record.team_id,
        user_id=record.created_by_user_id,
        allowed_models=tuple(record.allowed_models or ()),
        allowed_capabilities=caps,
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
    return await _gateway_principal_from_vkey_plain(plain, db)


@dataclass(frozen=True)
class VkeyOrApikeyPrincipal:
    """同时支持 sk-gw-... 和 sk-...（带 gateway:proxy scope）的认证结果"""

    via: GatewayInboundVia
    user_id: uuid.UUID | None
    team_id: uuid.UUID
    vkey: VirtualKeyPrincipal | None = None
    platform_api_key_id: uuid.UUID | None = None
    api_key_grant: ApiKeyGatewayGrantPrincipal | None = None


async def bearer_vkey_or_apikey_auth(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_optional_security)],
    db: Annotated[AsyncSession, Depends(get_db)],
    x_team_id: Annotated[str | None, Header(alias="X-Team-Id")] = None,
    x_api_key: Annotated[str | None, Header(alias="x-api-key")] = None,
) -> VkeyOrApikeyPrincipal:
    """同时支持 sk-gw-... 与 sk- + gateway:proxy scope

    sk- 时使用 X-Team-Id 头指定团队（默认 personal team）。

    认证来源：``Authorization: Bearer <token>`` 或 ``x-api-key: <token>``（优先 Bearer）。
    """
    plain = pick_gateway_proxy_plain_token(credentials, x_api_key)

    if is_vkey_format(plain):
        gp = await _gateway_principal_from_vkey_plain(plain, db)
        return VkeyOrApikeyPrincipal(
            via="vkey",
            user_id=gp.user_id,
            team_id=gp.team_id,
            vkey=gp.vkey,
            platform_api_key_id=None,
        )

    access = GatewayAccessUseCase(db)
    try:
        auth = await access.authenticate_platform_sk_for_gateway_proxy(plain, x_team_id)
    except HttpMappableDomainError as exc:
        raise http_exception_from_gateway_domain(exc) from exc

    try:
        grant_caps = allowed_capabilities_from_storage(auth.allowed_capabilities)
    except ValueError:
        logger.exception(
            "api key gateway grant %s has invalid allowed_capabilities in DB",
            auth.grant_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invalid API key Gateway grant capability configuration",
        ) from None

    set_permission_context(
        PermissionContext(
            user_id=auth.user_id,
            anonymous_user_id=None,
            role="user",
            team_id=auth.team_id,
            team_role=auth.team_role,
        )
    )

    return VkeyOrApikeyPrincipal(
        via="apikey",
        user_id=auth.user_id,
        team_id=auth.team_id,
        platform_api_key_id=auth.api_key_id,
        api_key_grant=ApiKeyGatewayGrantPrincipal(
            grant_id=auth.grant_id,
            api_key_id=auth.api_key_id,
            team_id=auth.team_id,
            user_id=auth.user_id,
            allowed_models=auth.allowed_models,
            allowed_capabilities=grant_caps,
            rpm_limit=auth.rpm_limit,
            tpm_limit=auth.tpm_limit,
            store_full_messages=auth.store_full_messages,
            guardrail_enabled=auth.guardrail_enabled,
        ),
    )


# 团队上下文见 ``domains.tenancy.presentation.team_dependencies``（由上方 import 再导出）。
