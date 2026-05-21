"""team_target 策略单元测试。"""

from __future__ import annotations

import uuid

from domains.tenancy.domain.policies.team_target import parse_team_id_header


def test_parse_prefers_path_over_header() -> None:
    tid = uuid.uuid4()
    other = uuid.uuid4()
    assert parse_team_id_header(str(tid), str(other)) == tid


def test_parse_header_when_no_path() -> None:
    tid = uuid.uuid4()
    assert parse_team_id_header(None, str(tid)) == tid


def test_parse_invalid_returns_none() -> None:
    assert parse_team_id_header("not-uuid", None) is None
