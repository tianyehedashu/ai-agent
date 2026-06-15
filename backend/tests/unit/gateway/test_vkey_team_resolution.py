"""vkey_team_resolution.dispatch_vkey_model 单测。"""

from __future__ import annotations

import uuid

import pytest

from bootstrap.config import settings
from domains.gateway.application.vkey_team_resolution import (
    assert_vkey_model_not_ambiguous,
    dispatch_vkey_model,
)
from domains.gateway.domain.errors import VkeyAmbiguousModelError, VkeyTeamPrefixUnknownError
from domains.gateway.domain.types import GatewayCapability, VirtualKeyPrincipal
from domains.tenancy.application.team_service import TeamService


def _vkey(
    *,
    team_id: uuid.UUID,
    granted: tuple[uuid.UUID, ...],
    is_system: bool = False,
) -> VirtualKeyPrincipal:
    return VirtualKeyPrincipal(
        vkey_id=uuid.uuid4(),
        vkey_name="k",
        team_id=team_id,
        user_id=uuid.uuid4(),
        allowed_models=(),
        allowed_capabilities=(GatewayCapability.CHAT,),
        rpm_limit=None,
        tpm_limit=None,
        store_full_messages=False,
        guardrail_enabled=False,
        is_system=is_system,
        granted_team_ids=granted,
    )


@pytest.mark.asyncio
async def test_dispatch_no_prefix_falls_to_bound_team(db_session, test_user) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    vkey = _vkey(team_id=team.id, granted=(team.id,))
    out = await dispatch_vkey_model(db_session, vkey=vkey, raw_model="gpt-4o")
    assert out.effective_team_id == team.id
    assert out.real_model_name == "gpt-4o"
    assert out.matched_slug is None


@pytest.mark.asyncio
async def test_dispatch_slug_hit_in_grants(db_session, test_user) -> None:
    teams = TeamService(db_session)
    primary = await teams.ensure_personal_team(test_user.id)
    shared = await teams.create_team(
        name=f"shared-{uuid.uuid4().hex[:6]}",
        owner_user_id=test_user.id,
    )
    vkey = _vkey(team_id=primary.id, granted=(primary.id, shared.id))
    out = await dispatch_vkey_model(
        db_session,
        vkey=vkey,
        raw_model=f"{shared.slug}/gpt-4o",
    )
    assert out.effective_team_id == shared.id
    assert out.real_model_name == "gpt-4o"
    assert out.matched_slug == shared.slug


@pytest.mark.asyncio
async def test_dispatch_vendor_prefix_not_in_grants_falls_to_bound(db_session, test_user) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    vkey = _vkey(team_id=team.id, granted=(team.id,))
    out = await dispatch_vkey_model(db_session, vkey=vkey, raw_model="openai/gpt-4o")
    assert out.effective_team_id == team.id
    assert out.real_model_name == "openai/gpt-4o"
    assert out.matched_slug is None


@pytest.mark.asyncio
async def test_dispatch_system_vkey_skips_prefix(db_session, test_user) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    vkey = _vkey(team_id=team.id, granted=(team.id,), is_system=True)
    out = await dispatch_vkey_model(db_session, vkey=vkey, raw_model="any-slug/model")
    assert out.effective_team_id == team.id
    assert out.real_model_name == "any-slug/model"


@pytest.mark.asyncio
async def test_dispatch_strict_unknown_slug_raises(
    db_session, test_user, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "gateway_vkey_strict_team_prefix", True)
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    vkey = _vkey(team_id=team.id, granted=(team.id,))
    with pytest.raises(VkeyTeamPrefixUnknownError):
        await dispatch_vkey_model(
            db_session,
            vkey=vkey,
            raw_model="unknown-team/gpt-4o",
            strict=True,
        )


@pytest.mark.asyncio
async def test_dispatch_empty_model(db_session, test_user) -> None:
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    vkey = _vkey(team_id=team.id, granted=(team.id,))
    out = await dispatch_vkey_model(db_session, vkey=vkey, raw_model="")
    assert out.effective_team_id == team.id
    assert out.real_model_name == ""


@pytest.mark.asyncio
async def test_assert_ambiguous_non_strict_records_metric_only(
    db_session, test_user,
) -> None:
    """非 strict：记指标但不拒绝。"""
    from domains.gateway.application import vkey_team_resolution as mod
    from domains.gateway.application.gateway_vkey_metrics import (
        export_vkey_metrics,
        reset_vkey_metrics_for_tests,
    )

    reset_vkey_metrics_for_tests()
    teams = TeamService(db_session)
    primary = await teams.ensure_personal_team(test_user.id)
    shared = await teams.create_team(
        name=f"shared-{uuid.uuid4().hex[:6]}",
        owner_user_id=test_user.id,
    )
    vkey = _vkey(team_id=primary.id, granted=(primary.id, shared.id))
    dispatch = await dispatch_vkey_model(db_session, vkey=vkey, raw_model="dup-model")

    async def _fake_count(_session, _ids, name: str) -> int:
        return 2 if name == "dup-model" else 0

    original = mod.count_grant_teams_with_model
    mod.count_grant_teams_with_model = _fake_count  # type: ignore[method-assign]
    try:
        await assert_vkey_model_not_ambiguous(
            db_session, vkey=vkey, dispatch=dispatch, strict=False
        )
        assert export_vkey_metrics()
    finally:
        mod.count_grant_teams_with_model = original


@pytest.mark.asyncio
async def test_assert_ambiguous_strict_raises(db_session, test_user) -> None:
    from domains.gateway.application import vkey_team_resolution as mod

    teams = TeamService(db_session)
    primary = await teams.ensure_personal_team(test_user.id)
    shared = await teams.create_team(
        name=f"shared-{uuid.uuid4().hex[:6]}",
        owner_user_id=test_user.id,
    )
    vkey = _vkey(team_id=primary.id, granted=(primary.id, shared.id))

    async def _fake_count(_session, _ids, name: str) -> int:
        return 2 if name == "dup-model" else 0

    original = mod.count_grant_teams_with_model
    mod.count_grant_teams_with_model = _fake_count  # type: ignore[method-assign]
    try:
        dispatch_dup = await dispatch_vkey_model(db_session, vkey=vkey, raw_model="dup-model")
        with pytest.raises(VkeyAmbiguousModelError):
            await assert_vkey_model_not_ambiguous(
                db_session, vkey=vkey, dispatch=dispatch_dup, strict=True
            )
    finally:
        mod.count_grant_teams_with_model = original
