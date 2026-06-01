"""giikin SSO 会话 Cookie 解析（guard_token → Redis user:session:*）。

**仅用于开发/应急**：`GIIKIN_SESSION_COOKIE_FALLBACK=true` 且未部署 auth-bridge 时。
生产身份应由 HiGress giikin-auth-bridge 注入 X-Giikin-* Header，backend 不应直连 IAM Redis。
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from libs.db.redis import get_redis_client
from utils.logging import get_logger

if TYPE_CHECKING:
    from fastapi import Request

    from domains.identity.infrastructure.auth.giikin_gateway import GiikinGatewayClaims

logger = get_logger(__name__)

SESSION_KEY_PREFIX = "user:session:"
GIKIN_SESSION_KEY_PREFIX = "giikin:user:session:"


def _extract_cookie(request: Request, cookie_name: str) -> str | None:
    token = request.cookies.get(cookie_name)
    if token and token.strip():
        return token.strip()
    return None


def _parse_session_payload(raw: str) -> dict[str, object] | None:
    """解析 Redis 中的 session JSON（兼容 Redisson 字符串序列化）。"""
    text = raw.strip()
    if not text:
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return None
    return payload if isinstance(payload, dict) else None


def _claims_from_payload(payload: dict[str, object]) -> GiikinGatewayClaims | None:
    from domains.identity.infrastructure.auth.giikin_gateway import GiikinGatewayClaims

    user_id = str(payload.get("user_id", "")).strip()
    if not user_id:
        return None
    name = str(payload.get("name", "")).strip()
    org_code = str(payload.get("org_code", "")).strip()
    shop_id = str(payload.get("shop_id", "")).strip()
    return GiikinGatewayClaims(
        user_id=user_id,
        name=name or f"Giikin {user_id}",
        org_code=org_code,
        shop_id=shop_id,
    )


async def resolve_claims_from_session_cookie(
    request: Request,
    *,
    cookie_name: str = "guard_token",
) -> GiikinGatewayClaims | None:
    """从 guard_token Cookie + Redis 解析 giikin 身份；无 Cookie 或会话无效返回 None。"""
    token = _extract_cookie(request, cookie_name)
    if not token:
        return None

    client = await get_redis_client()
    for prefix in (SESSION_KEY_PREFIX, GIKIN_SESSION_KEY_PREFIX):
        raw = await client.get(f"{prefix}{token}")
        if not raw:
            continue
        payload = _parse_session_payload(raw)
        if payload is None:
            logger.warning("Invalid giikin session payload in Redis for key prefix %s", prefix)
            continue
        claims = _claims_from_payload(payload)
        if claims is not None:
            return claims
    return None


__all__ = ["resolve_claims_from_session_cookie"]
