"""MCP 访问策略单测。"""

import pytest

from domains.agent.domain.policies.mcp_access import (
    McpAccessAction,
    McpServerKind,
    assert_mcp_access,
    assert_mcp_delete,
)
from libs.exceptions import PermissionDeniedError


def test_user_server_mutate_allowed() -> None:
    assert_mcp_access(
        kind=McpServerKind.USER,
        is_platform_admin=False,
        action=McpAccessAction.MUTATE,
    )


def test_system_read_tools_allowed_for_non_admin() -> None:
    assert_mcp_access(
        kind=McpServerKind.SYSTEM,
        is_platform_admin=False,
        action=McpAccessAction.READ_TOOLS,
    )


def test_system_mutate_denied_for_non_admin() -> None:
    with pytest.raises(PermissionDeniedError) as exc:
        assert_mcp_access(
            kind=McpServerKind.SYSTEM,
            is_platform_admin=False,
            action=McpAccessAction.MUTATE,
        )
    assert exc.value.code == "CANNOT_UPDATE_SYSTEM_SERVER"


def test_system_mutate_allowed_for_admin() -> None:
    assert_mcp_access(
        kind=McpServerKind.SYSTEM,
        is_platform_admin=True,
        action=McpAccessAction.MUTATE,
    )


def test_system_delete_denied_for_non_admin() -> None:
    with pytest.raises(PermissionDeniedError) as exc:
        assert_mcp_delete(kind=McpServerKind.SYSTEM, is_platform_admin=False)
    assert exc.value.code == "CANNOT_DELETE_SYSTEM_SERVER"
