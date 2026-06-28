"""测试用 Gateway 桥接归因 patch（非 conftest，可供 integration/e2e 复用）。"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import patch
import uuid


@contextmanager
def patch_bridge_identity(
    user_id: uuid.UUID | None = None,
    team_id: uuid.UUID | None = None,
) -> Iterator[uuid.UUID]:
    """模拟内部桥接可归因的 user/team（与 PermissionContext 解耦）。"""
    uid = user_id or uuid.uuid4()
    tid = team_id
    targets = [
        "domains.agent.infrastructure.llm.agent_llm_facade.resolve_internal_gateway_user_id",
        "domains.gateway.application.bridge.bridge_attribution.resolve_internal_gateway_user_id",
    ]
    team_targets = [
        "domains.gateway.application.bridge.bridge_attribution.resolve_internal_gateway_team_id",
    ]
    with (
        patch(targets[0], return_value=uid),
        patch(targets[1], return_value=uid),
        patch(team_targets[0], return_value=tid),
    ):
        yield uid
