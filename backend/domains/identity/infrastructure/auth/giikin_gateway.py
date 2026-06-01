"""giikin 网关身份解析。

生产经 HiGress(giikin-auth-bridge) 注入身份 Header；本模块负责：
- 校验 ``X-Giikin-Internal-Key``（防绕过网关直连伪造身份）
- 解码 ``X-Giikin-User-JSON``（Base64 JSON）得到 giikin 用户信息

不在此处做用户落库；JIT 映射见 ``application/giikin_identity_service``。
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
import json
from typing import TYPE_CHECKING

from libs.exceptions import AuthenticationError
from utils.logging import get_logger

if TYPE_CHECKING:
    from fastapi import Request

    from bootstrap.config import Settings

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class GiikinGatewayClaims:
    """HiGress 注入的 giikin 身份视图。"""

    user_id: str
    name: str
    org_code: str
    shop_id: str


def _decode_user_json(raw: str) -> dict[str, object]:
    """解码 Base64(JSON)；失败抛 AuthenticationError。"""
    try:
        decoded = base64.b64decode(raw, validate=True)
        payload = json.loads(decoded.decode("utf-8"))
    except (binascii.Error, ValueError, UnicodeDecodeError) as exc:
        raise AuthenticationError("Invalid gateway identity header") from exc
    if not isinstance(payload, dict):
        raise AuthenticationError("Invalid gateway identity header")
    return payload


def parse_gateway_identity(
    request: Request,
    settings: Settings,
) -> GiikinGatewayClaims | None:
    """从请求 Header 解析 giikin 身份。

    返回 None 表示请求未携带任何 giikin 身份 Header（交由上层决定是否 401）。
    若携带身份 Header 但 Internal-Key 缺失/不匹配，则抛 ``AuthenticationError``。
    """
    headers = request.headers
    user_json = headers.get(settings.giikin_user_json_header)
    user_id_header = headers.get(settings.giikin_user_id_header)

    if not user_json and not user_id_header:
        return None

    # 防直连伪造：配置了 internal_key 时必须匹配
    expected_key = (
        settings.giikin_internal_key.get_secret_value()
        if settings.giikin_internal_key is not None
        else None
    )
    if expected_key:
        provided = headers.get(settings.giikin_internal_key_header)
        if not provided or provided != expected_key:
            logger.warning("Gateway identity present but internal key invalid/missing")
            raise AuthenticationError("Invalid gateway internal key")

    if user_json:
        payload = _decode_user_json(user_json)
        user_id = str(payload.get("user_id", "")).strip()
        name = str(payload.get("name", "")).strip()
        org_code = str(payload.get("org_code", "")).strip()
        shop_id = str(payload.get("shop_id", "")).strip()
    else:
        user_id = (user_id_header or "").strip()
        name = ""
        org_code = ""
        shop_id = ""

    if not user_id:
        raise AuthenticationError("Gateway identity missing user_id")

    return GiikinGatewayClaims(
        user_id=user_id,
        name=name or f"Giikin {user_id}",
        org_code=org_code,
        shop_id=shop_id,
    )


async def resolve_giikin_identity(
    request: Request,
    settings: Settings,
) -> GiikinGatewayClaims | None:
    """解析 giikin 身份：生产仅信任 HiGress 注入 Header；开发可开 cookie 回退。"""
    claims = parse_gateway_identity(request, settings)
    if claims is not None:
        return claims

    if not settings.giikin_session_cookie_fallback:
        return None

    from domains.identity.infrastructure.auth.giikin_session_cookie import (
        resolve_claims_from_session_cookie,
    )

    cookie_name = settings.giikin_session_cookie_name
    return await resolve_claims_from_session_cookie(request, cookie_name=cookie_name)


__all__ = ["GiikinGatewayClaims", "parse_gateway_identity", "resolve_giikin_identity"]
