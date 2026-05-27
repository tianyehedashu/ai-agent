"""匿名用户 tenant_id 解析（纯函数，无 IO）。

匿名身份不落 ``users`` / ``gateway_teams``；业务数据以确定性 UUID v5 作为 ``tenant_id``。
"""

from __future__ import annotations

import uuid

from domains.identity.domain.types import Principal

# 项目专用 namespace；勿与 personal team 随机 UUID 混用。
ANONYMOUS_TENANT_NAMESPACE = uuid.UUID("01932f8a-7b3c-7000-8000-000000000001")


def normalize_anonymous_cookie_id(raw: str) -> str:
    """规范化 cookie / header 中的匿名 ID（去除 ``anonymous-`` 前缀）。"""
    return Principal.extract_anonymous_id(raw.strip())


def resolve_anonymous_tenant_id(cookie_id: str) -> uuid.UUID:
    """由匿名 cookie ID 确定性解析 ``tenant_id``（不落库）。"""
    normalized = normalize_anonymous_cookie_id(cookie_id)
    return uuid.uuid5(ANONYMOUS_TENANT_NAMESPACE, normalized)


def anonymous_team_ids(cookie_id: str) -> frozenset[uuid.UUID]:
    """供 ``PermissionContext.team_ids`` 使用的匿名 tenant 集合。"""
    return frozenset({resolve_anonymous_tenant_id(cookie_id)})


__all__ = [
    "ANONYMOUS_TENANT_NAMESPACE",
    "anonymous_team_ids",
    "normalize_anonymous_cookie_id",
    "resolve_anonymous_tenant_id",
]
