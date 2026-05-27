"""anonymous_tenant 纯函数测试。"""

from __future__ import annotations

import uuid

from domains.identity.domain.anonymous_tenant import (
    anonymous_team_ids,
    normalize_anonymous_cookie_id,
    resolve_anonymous_tenant_id,
)


def test_normalize_strips_anonymous_prefix() -> None:
    raw = "abc-123"
    assert normalize_anonymous_cookie_id(f"anonymous-{raw}") == raw
    assert normalize_anonymous_cookie_id(raw) == raw


def test_resolve_tenant_id_is_idempotent() -> None:
    cookie = str(uuid.uuid4())
    t1 = resolve_anonymous_tenant_id(cookie)
    t2 = resolve_anonymous_tenant_id(f"anonymous-{cookie}")
    assert t1 == t2


def test_different_cookies_different_tenants() -> None:
    a = resolve_anonymous_tenant_id(str(uuid.uuid4()))
    b = resolve_anonymous_tenant_id(str(uuid.uuid4()))
    assert a != b


def test_anonymous_team_ids_singleton() -> None:
    cookie = str(uuid.uuid4())
    ids = anonymous_team_ids(cookie)
    assert ids == frozenset({resolve_anonymous_tenant_id(cookie)})
