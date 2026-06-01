"""测试用 Giikin SSO Header 构造（integration / e2e 复用）。"""

from __future__ import annotations

import base64
import json

# 与 conftest ``sso_client`` fixture 中 patch 的 internal key 一致
GIIKIN_SSO_TEST_INTERNAL_KEY = "test-internal-key-for-pytest"


def encode_giikin_user_json(
    *,
    user_id: str,
    name: str = "SSO Test User",
    org_code: str = "",
    shop_id: str = "",
) -> str:
    """Base64(JSON) 与 HiGress giikin-auth-bridge 注入格式一致。"""
    payload = {
        "user_id": user_id,
        "name": name,
        "org_code": org_code,
        "shop_id": shop_id,
    }
    return base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")


def giikin_sso_headers(
    *,
    user_id: str,
    name: str = "SSO Test User",
    org_code: str = "",
    shop_id: str = "",
    internal_key: str = GIIKIN_SSO_TEST_INTERNAL_KEY,
) -> dict[str, str]:
    """构造 SSO 模式 ``GET /auth/me`` 等请求所需的 Giikin 身份 Header。"""
    return {
        "X-Giikin-User-JSON": encode_giikin_user_json(
            user_id=user_id,
            name=name,
            org_code=org_code,
            shop_id=shop_id,
        ),
        "X-Giikin-Internal-Key": internal_key,
    }


__all__ = [
    "GIIKIN_SSO_TEST_INTERNAL_KEY",
    "encode_giikin_user_json",
    "giikin_sso_headers",
]
