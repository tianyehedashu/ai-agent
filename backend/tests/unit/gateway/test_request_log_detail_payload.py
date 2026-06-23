"""custom_logger：success 默认不落库详情 JSONB 的规则。"""

from __future__ import annotations

from domains.gateway.infrastructure.callbacks.custom_logger import (
    _should_build_detail_jsonb,
    resolve_detail_jsonb_for_persist,
)

_TEAM_SNAP = {"name": "Acme", "kind": "team"}
_ROUTE_SNAP = {"virtual_model": "gpt-4o", "primary_models": ["gpt-4o"]}
_RESPONSE_SUMMARY = {"preview": "hello"}
_METADATA_EXTRA = {"session_id": "sess-1"}


def test_resolve_detail_jsonb_success_default_strips_payload() -> None:
    team, route, response, extra = resolve_detail_jsonb_for_persist(
        status="success",
        persist_detail_jsonb=False,
        verbose_log=False,
        team_snapshot=_TEAM_SNAP,
        route_snapshot=_ROUTE_SNAP,
        response_summary=_RESPONSE_SUMMARY,
        metadata_extra=_METADATA_EXTRA,
    )
    assert team is None
    assert route is None
    assert response is None
    assert extra is None


def test_resolve_detail_jsonb_failed_keeps_payload_when_config_off() -> None:
    team, route, response, extra = resolve_detail_jsonb_for_persist(
        status="failed",
        persist_detail_jsonb=False,
        verbose_log=False,
        team_snapshot=_TEAM_SNAP,
        route_snapshot=_ROUTE_SNAP,
        response_summary=_RESPONSE_SUMMARY,
        metadata_extra=_METADATA_EXTRA,
    )
    assert team == _TEAM_SNAP
    assert route == _ROUTE_SNAP
    assert response == _RESPONSE_SUMMARY
    assert extra == _METADATA_EXTRA


def test_resolve_detail_jsonb_success_verbose_keeps_payload() -> None:
    team, route, response, extra = resolve_detail_jsonb_for_persist(
        status="success",
        persist_detail_jsonb=False,
        verbose_log=True,
        team_snapshot=_TEAM_SNAP,
        route_snapshot=_ROUTE_SNAP,
        response_summary=_RESPONSE_SUMMARY,
        metadata_extra=_METADATA_EXTRA,
    )
    assert team == _TEAM_SNAP
    assert route == _ROUTE_SNAP
    assert response == _RESPONSE_SUMMARY
    assert extra == _METADATA_EXTRA


def test_resolve_detail_jsonb_success_config_on_keeps_payload() -> None:
    team, route, response, extra = resolve_detail_jsonb_for_persist(
        status="success",
        persist_detail_jsonb=True,
        verbose_log=False,
        team_snapshot=_TEAM_SNAP,
        route_snapshot=_ROUTE_SNAP,
        response_summary=_RESPONSE_SUMMARY,
        metadata_extra=_METADATA_EXTRA,
    )
    assert team == _TEAM_SNAP
    assert route == _ROUTE_SNAP
    assert response == _RESPONSE_SUMMARY
    assert extra == _METADATA_EXTRA


def test_should_build_detail_jsonb_matches_resolve_rules() -> None:
    assert not _should_build_detail_jsonb(
        status="success",
        verbose_log=False,
        persist_detail_jsonb=False,
    )
    assert _should_build_detail_jsonb(
        status="failed",
        verbose_log=False,
        persist_detail_jsonb=False,
    )
    assert _should_build_detail_jsonb(
        status="success",
        verbose_log=True,
        persist_detail_jsonb=False,
    )
    assert _should_build_detail_jsonb(
        status="success",
        verbose_log=False,
        persist_detail_jsonb=True,
    )
