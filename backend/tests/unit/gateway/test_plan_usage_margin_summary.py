"""GatewayPlanUsageReadService.get_team_margin_summary 单测。"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from domains.gateway.application.management.usage_reads import GatewayPlanUsageReadService
from domains.gateway.infrastructure.repositories.credential_repository import (
    ProviderCredentialRepository,
)


@pytest.mark.asyncio
async def test_get_team_margin_summary_resolves_credential_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    team_id = uuid.uuid4()
    cred_id = uuid.uuid4()
    row = SimpleNamespace(
        group_key=cred_id,
        cost_usd=Decimal("0.5"),
        credential_name_snapshot="历史快照",
    )
    exec_result = MagicMock()
    exec_result.all.return_value = [row]
    session = AsyncMock()
    session.execute = AsyncMock(return_value=exec_result)

    cred = SimpleNamespace(id=cred_id, name="生产凭据")

    async def fake_list_by_ids(
        self: ProviderCredentialRepository, credential_ids: list[uuid.UUID]
    ) -> list[SimpleNamespace]:
        assert credential_ids == [cred_id]
        return [cred]

    monkeypatch.setattr(ProviderCredentialRepository, "list_by_ids", fake_list_by_ids)

    svc = GatewayPlanUsageReadService(session)
    summary = await svc.get_team_margin_summary(team_id, group_by="credential")

    assert summary.group_by == "credential"
    assert summary.group_column_label == "凭据"
    assert len(summary.items) == 1
    assert summary.items[0].group_key == str(cred_id)
    assert summary.items[0].label == "生产凭据"
    assert summary.items[0].cost_usd == Decimal("0.5")


@pytest.mark.asyncio
async def test_get_team_margin_summary_unlinked_credential_label() -> None:
    team_id = uuid.uuid4()
    row = SimpleNamespace(
        group_key=None,
        cost_usd=Decimal("0.1"),
        credential_name_snapshot=None,
    )
    exec_result = MagicMock()
    exec_result.all.return_value = [row]
    session = AsyncMock()
    session.execute = AsyncMock(return_value=exec_result)

    summary = await GatewayPlanUsageReadService(session).get_team_margin_summary(
        team_id, group_by="credential"
    )

    assert summary.items[0].group_key == ""
    assert summary.items[0].label == "未关联凭据"


@pytest.mark.asyncio
async def test_get_team_margin_summary_team_names_via_team_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    team_id = uuid.uuid4()
    row = SimpleNamespace(group_key=team_id, cost_usd=Decimal("1"))
    exec_result = MagicMock()
    exec_result.all.return_value = [row]
    session = AsyncMock()
    session.execute = AsyncMock(return_value=exec_result)

    mock_svc = MagicMock()
    mock_svc.get_display_names_by_ids = AsyncMock(return_value={team_id: "研发团队"})

    def fake_team_service(_session: object) -> MagicMock:
        return mock_svc

    monkeypatch.setattr(
        "domains.gateway.application.management.usage_reads.TeamService",
        fake_team_service,
    )

    summary = await GatewayPlanUsageReadService(session).get_team_margin_summary(
        team_id, group_by="team"
    )

    mock_svc.get_display_names_by_ids.assert_awaited_once_with([team_id])
    assert summary.items[0].label == "研发团队"
