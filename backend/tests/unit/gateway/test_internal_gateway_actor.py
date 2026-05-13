"""resolve_internal_gateway_user_id 行为。"""

import uuid

from domains.gateway.application.internal_bridge_actor import (
    resolve_internal_gateway_team_id,
    resolve_internal_gateway_user_id,
)
from libs.db.permission_context import (
    PermissionContext,
    clear_permission_context,
    set_permission_context,
)


def test_resolve_prefers_registered_user_id() -> None:
    uid = uuid.uuid4()
    try:
        set_permission_context(PermissionContext(user_id=uid, role="user"))
        assert resolve_internal_gateway_user_id() == uid
    finally:
        clear_permission_context()


def test_resolve_returns_none_without_context_or_delegate() -> None:
    try:
        clear_permission_context()
        assert resolve_internal_gateway_user_id() is None
    finally:
        clear_permission_context()


def test_resolve_team_id_from_permission_context() -> None:
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
        assert resolve_internal_gateway_team_id() == tid
    finally:
        clear_permission_context()


def test_resolve_team_id_none_without_team_on_context() -> None:
    uid = uuid.uuid4()
    try:
        set_permission_context(PermissionContext(user_id=uid, role="user"))
        assert resolve_internal_gateway_team_id() is None
    finally:
        clear_permission_context()
