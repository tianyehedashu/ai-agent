"""套餐毛利分组标签解析单元测试。"""

from __future__ import annotations

from uuid import UUID

from domains.gateway.domain.margin_read_model import (
    margin_group_column_label,
    resolve_margin_group_label,
)

_CRED_ID = UUID("11111111-1111-1111-1111-111111111111")
_TEAM_ID = UUID("22222222-2222-2222-2222-222222222222")


def test_margin_group_column_label() -> None:
    assert margin_group_column_label("credential") == "凭据"
    assert margin_group_column_label("model") == "模型"
    assert margin_group_column_label("team") == "团队"


def test_resolve_credential_null_is_unlinked() -> None:
    key, label = resolve_margin_group_label("credential", None)
    assert key == ""
    assert label == "未关联凭据"


def test_resolve_credential_prefers_db_name() -> None:
    key, label = resolve_margin_group_label(
        "credential",
        _CRED_ID,
        credential_names={_CRED_ID: "OpenAI 生产"},
        credential_name_snapshot="旧快照",
    )
    assert key == str(_CRED_ID)
    assert label == "OpenAI 生产"


def test_resolve_credential_falls_back_to_snapshot() -> None:
    key, label = resolve_margin_group_label(
        "credential",
        _CRED_ID,
        credential_names={},
        credential_name_snapshot="  历史凭据名  ",
    )
    assert key == str(_CRED_ID)
    assert label == "历史凭据名"


def test_resolve_credential_falls_back_to_short_id() -> None:
    key, label = resolve_margin_group_label("credential", _CRED_ID, credential_names={})
    assert key == str(_CRED_ID)
    assert label == "11111111…"


def test_resolve_model_null_is_unknown() -> None:
    key, label = resolve_margin_group_label("model", None)
    assert key == ""
    assert label == "未知模型"


def test_resolve_model_uses_model_string() -> None:
    key, label = resolve_margin_group_label("model", "gpt-4o")
    assert key == "gpt-4o"
    assert label == "gpt-4o"


def test_resolve_team_uses_team_name() -> None:
    key, label = resolve_margin_group_label(
        "team",
        _TEAM_ID,
        team_names={_TEAM_ID: "研发团队"},
    )
    assert key == str(_TEAM_ID)
    assert label == "研发团队"
