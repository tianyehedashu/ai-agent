"""pricing_model_enrichment / pricing_read_mappers 单元测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest

from domains.gateway.application.pricing.pricing_model_enrichment import (
    PricingModelRef,
    build_pricing_model_ref_map,
)
from domains.gateway.application.pricing.pricing_read_mappers import (
    merge_model_ref_into_payload,
    pricing_model_ref_to_api_dict,
)
from domains.gateway.infrastructure.models.gateway_model import GatewayModel
from domains.gateway.infrastructure.models.system_gateway import SystemGatewayModel


def test_pricing_model_ref_to_api_dict() -> None:
    cred_id = uuid.uuid4()
    ref = PricingModelRef(
        gateway_model_id=uuid.uuid4(),
        model_name="gpt-test",
        provider="openai",
        credential_id=cred_id,
        credential_name="prod-key",
        registry_kind="team",
        real_model="gpt-4o",
        capability="chat",
    )
    payload = pricing_model_ref_to_api_dict(ref)
    assert payload["model_name"] == "gpt-test"
    assert payload["provider"] == "openai"
    assert payload["credential_id"] == cred_id
    assert payload["credential_name"] == "prod-key"
    assert payload["registry_kind"] == "team"


def test_merge_model_ref_into_payload_noop_when_ref_missing() -> None:
    base = {"gateway_model_id": uuid.uuid4(), "inheritance_strategy": "mirror"}
    assert merge_model_ref_into_payload(base, None) == base


def test_merge_model_ref_into_payload_merges_fields() -> None:
    model_id = uuid.uuid4()
    base = {"gateway_model_id": model_id, "inheritance_strategy": "manual"}
    ref = PricingModelRef(
        gateway_model_id=model_id,
        model_name="demo",
        provider="deepseek",
        credential_id=uuid.uuid4(),
        credential_name="main",
        registry_kind="team",
        real_model="deepseek-chat",
        capability="chat",
    )
    merged = merge_model_ref_into_payload(base, ref)
    assert merged["model_name"] == "demo"
    assert merged["provider"] == "deepseek"
    assert merged["credential_name"] == "main"


@pytest.mark.asyncio
async def test_build_pricing_model_ref_map_team_and_system() -> None:
    team_model_id = uuid.uuid4()
    system_model_id = uuid.uuid4()
    team_cred_id = uuid.uuid4()
    system_cred_id = uuid.uuid4()
    tenant_id = uuid.uuid4()

    team_row = MagicMock(spec=GatewayModel)
    team_row.id = team_model_id
    team_row.name = "team-model"
    team_row.provider = "deepseek"
    team_row.credential_id = team_cred_id
    team_row.real_model = "deepseek-chat"
    team_row.capability = "chat"
    team_row.tenant_id = tenant_id

    system_row = MagicMock(spec=SystemGatewayModel)
    system_row.id = system_model_id
    system_row.name = "system-model"
    system_row.provider = "openai"
    system_row.credential_id = system_cred_id
    system_row.real_model = "gpt-4o"
    system_row.capability = "chat"
    system_row.tenant_id = None

    team_result = MagicMock()
    team_result.scalars.return_value.all.return_value = [team_row]
    system_result = MagicMock()
    system_result.scalars.return_value.all.return_value = [system_row]

    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[team_result, system_result])

    team_cred = MagicMock()
    team_cred.id = team_cred_id
    team_cred.name = "team-cred"
    system_cred = MagicMock()
    system_cred.id = system_cred_id
    system_cred.name = "system-cred"

    with (
        patch(
            "domains.gateway.application.pricing.pricing_model_enrichment.ProviderCredentialRepository"
        ) as team_cred_repo_cls,
        patch(
            "domains.gateway.application.pricing.pricing_model_enrichment.SystemProviderCredentialRepository"
        ) as system_cred_repo_cls,
    ):
        team_cred_repo_cls.return_value.list_by_ids = AsyncMock(return_value=[team_cred])
        system_cred_repo_cls.return_value.list_by_ids = AsyncMock(return_value=[system_cred])

        ref_map = await build_pricing_model_ref_map(
            session,
            {team_model_id, system_model_id},
            tenant_id=tenant_id,
        )

    assert ref_map[team_model_id].model_name == "team-model"
    assert ref_map[team_model_id].credential_name == "team-cred"
    assert ref_map[team_model_id].registry_kind == "team"
    assert ref_map[system_model_id].model_name == "system-model"
    assert ref_map[system_model_id].credential_name == "system-cred"
    assert ref_map[system_model_id].registry_kind == "system"


@pytest.mark.asyncio
async def test_build_pricing_model_ref_map_tenant_filter_excludes_foreign_team_model() -> None:
    foreign_model_id = uuid.uuid4()
    foreign_row = MagicMock(spec=GatewayModel)
    foreign_row.id = foreign_model_id

    team_result = MagicMock()
    team_result.scalars.return_value.all.return_value = []
    system_result = MagicMock()
    system_result.scalars.return_value.all.return_value = []

    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[team_result, system_result])

    ref_map = await build_pricing_model_ref_map(
        session,
        {foreign_model_id},
        tenant_id=uuid.uuid4(),
    )
    assert ref_map == {}


@pytest.mark.asyncio
async def test_build_pricing_model_ref_map_empty_ids() -> None:
    session = AsyncMock()
    ref_map = await build_pricing_model_ref_map(session, set())
    assert ref_map == {}
    session.execute.assert_not_called()
