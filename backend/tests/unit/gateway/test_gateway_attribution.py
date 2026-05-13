"""resolve_gateway_bridge_attribution 优先级与边界。"""

from __future__ import annotations

import uuid

import pytest

from domains.gateway.application.bridge_attribution import resolve_gateway_bridge_attribution
from libs.db.permission_context import (
    PermissionContext,
    clear_permission_context,
    set_permission_context,
)


def test_resolve_uses_permission_team_when_no_explicit() -> None:
    uid = uuid.uuid4()
    tid = uuid.uuid4()
    try:
        set_permission_context(
            PermissionContext(
                user_id=uid,
                role="user",
                team_id=tid,
                team_role="member",
            )
        )
        attr = resolve_gateway_bridge_attribution()
        assert attr.actor_user_id == uid
        assert attr.billing_team_id == tid
    finally:
        clear_permission_context()


def test_explicit_billing_overrides_permission_team() -> None:
    uid = uuid.uuid4()
    tid = uuid.uuid4()
    override = uuid.uuid4()
    try:
        set_permission_context(
            PermissionContext(
                user_id=uid,
                role="user",
                team_id=tid,
                team_role="member",
            )
        )
        attr = resolve_gateway_bridge_attribution(explicit_billing_team_id=override)
        assert attr.actor_user_id == uid
        assert attr.billing_team_id == override
    finally:
        clear_permission_context()


def test_billing_none_without_team_on_context() -> None:
    uid = uuid.uuid4()
    try:
        set_permission_context(PermissionContext(user_id=uid, role="user"))
        attr = resolve_gateway_bridge_attribution()
        assert attr.actor_user_id == uid
        assert attr.billing_team_id is None
    finally:
        clear_permission_context()


def test_raises_without_actor() -> None:
    try:
        clear_permission_context()
        with pytest.raises(ValueError, match="bridge attribution"):
            resolve_gateway_bridge_attribution()
    finally:
        clear_permission_context()
