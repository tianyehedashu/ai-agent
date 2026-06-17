"""平台预算 preflight 锚点 pin 单测。"""

from __future__ import annotations

import uuid

from domains.gateway.application.budget_platform_settlement import (
    deserialize_budget_anchor_pins,
    resolve_budget_commit_anchor,
    serialize_budget_anchor_pins,
)
from domains.gateway.domain.period_reset_anchor import (
    DEFAULT_PERIOD_RESET_ANCHOR,
    PeriodResetAnchor,
)


def test_resolve_budget_commit_anchor_prefers_pin() -> None:
    coord = ("tenant", uuid.uuid4(), "daily", None, None, None)
    pinned = {coord: PeriodResetAnchor(timezone="Asia/Shanghai", time_minutes=540, day_of_month=1)}
    resolved = resolve_budget_commit_anchor(
        coord,
        config_anchor=DEFAULT_PERIOD_RESET_ANCHOR,
        pinned_anchors=pinned,
    )
    assert resolved.timezone == "Asia/Shanghai"
    assert resolved.time_minutes == 540


def test_serialize_deserialize_anchor_pins_roundtrip() -> None:
    team_id = uuid.uuid4()
    coord = ("user", team_id, "monthly", "gpt-4", None, team_id)
    anchor = PeriodResetAnchor(timezone="UTC", time_minutes=120, day_of_month=15)
    pins = {coord: anchor}
    raw = serialize_budget_anchor_pins(pins)
    restored = deserialize_budget_anchor_pins(raw)
    assert restored[coord] == anchor
