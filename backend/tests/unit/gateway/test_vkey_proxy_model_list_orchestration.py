"""list_proxy_models_for_multi_grant_vkey 编排单测（homonym slug 与 dispatch 对齐）。"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest

from domains.gateway.application.vkey.virtual_key_proxy_model_list import (
    list_proxy_models_for_multi_grant_vkey,
)
from domains.gateway.domain.types import GatewayCapability, VirtualKeyPrincipal
from domains.gateway.infrastructure.models.gateway_model import GatewayModel


def _row(*, name: str, tenant_id: uuid.UUID) -> GatewayModel:
    return GatewayModel(
        name=name,
        capability="chat",
        real_model="gpt-4o-mini",
        credential_id=uuid.uuid4(),
        provider="openai",
        tenant_id=tenant_id,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _vkey(*, bound: uuid.UUID, grants: tuple[uuid.UUID, ...]) -> VirtualKeyPrincipal:
    return VirtualKeyPrincipal(
        vkey_id=uuid.uuid4(),
        vkey_name="k",
        team_id=bound,
        user_id=uuid.uuid4(),
        allowed_models=(),
        allowed_capabilities=(GatewayCapability.CHAT,),
        rpm_limit=None,
        tpm_limit=None,
        store_full_messages=False,
        guardrail_enabled=False,
        is_system=False,
        granted_team_ids=grants,
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_multi_grant_homonym_slug_skips_grant_team_models(db_session: object) -> None:
    bound = uuid.uuid4()
    grant_a = uuid.uuid4()
    grant_b = uuid.uuid4()
    dup_slug = "same-slug"
    bound_model = _row(name="bound-only", tenant_id=bound)
    grant_a_model = _row(name="grant-a-model", tenant_id=grant_a)
    grant_b_model = _row(name="grant-b-model", tenant_id=grant_b)

    reads = MagicMock()
    reads.list_gateway_models = AsyncMock(
        side_effect=lambda tenant_id, **kwargs: {
            bound: [bound_model],
            grant_a: [grant_a_model],
            grant_b: [grant_b_model],
        }[tenant_id]
    )
    reads.list_gateway_routes = AsyncMock(return_value=[])

    captured_models: list[GatewayModel] = []

    async def _capture_build(
        _session: object,
        models: list[GatewayModel],
        **kwargs: object,
    ) -> list[dict[str, object]]:
        captured_models.extend(models)
        return []

    with (
        patch(
            "domains.gateway.application.vkey.virtual_key_proxy_model_list.GatewayManagementReadService",
            return_value=reads,
        ),
        patch(
            "domains.gateway.application.vkey.virtual_key_proxy_model_list.fetch_grant_team_slug_rows",
            AsyncMock(
                return_value=[
                    (bound, "primary-slug"),
                    (grant_a, dup_slug),
                    (grant_b, dup_slug),
                ]
            ),
        ),
        patch(
            "domains.gateway.application.vkey.virtual_key_proxy_model_list.build_proxy_models_list",
            side_effect=_capture_build,
        ),
    ):
        await list_proxy_models_for_multi_grant_vkey(
            db_session,  # type: ignore[arg-type]
            vkey=_vkey(bound=bound, grants=(bound, grant_a, grant_b)),
            user_id=None,
            allowed=None,
            entitlement_scope=None,
            entitlement_scope_id=None,
        )

    assert [m.name for m in captured_models] == ["bound-only"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_multi_grant_unique_slug_includes_prefixed_grant_model(db_session: object) -> None:
    bound = uuid.uuid4()
    grant = uuid.uuid4()
    bound_model = _row(name="bound-only", tenant_id=bound)
    grant_model = _row(name="shared-model", tenant_id=grant)

    reads = MagicMock()
    reads.list_gateway_models = AsyncMock(
        side_effect=lambda tenant_id, **kwargs: {
            bound: [bound_model],
            grant: [grant_model],
        }[tenant_id]
    )
    reads.list_gateway_routes = AsyncMock(return_value=[])

    captured_ids: list[str] = []

    async def _capture_build(
        _session: object,
        models: list[GatewayModel],
        *,
        model_list_ids: list[str] | None = None,
        **kwargs: object,
    ) -> list[dict[str, object]]:
        if model_list_ids is not None:
            captured_ids.extend(model_list_ids)
        return []

    with (
        patch(
            "domains.gateway.application.vkey.virtual_key_proxy_model_list.GatewayManagementReadService",
            return_value=reads,
        ),
        patch(
            "domains.gateway.application.vkey.virtual_key_proxy_model_list.fetch_grant_team_slug_rows",
            AsyncMock(
                return_value=[
                    (bound, "primary-slug"),
                    (grant, "collab"),
                ]
            ),
        ),
        patch(
            "domains.gateway.application.vkey.virtual_key_proxy_model_list.build_proxy_models_list",
            side_effect=_capture_build,
        ),
    ):
        await list_proxy_models_for_multi_grant_vkey(
            db_session,  # type: ignore[arg-type]
            vkey=_vkey(bound=bound, grants=(bound, grant)),
            user_id=None,
            allowed=None,
            entitlement_scope=None,
            entitlement_scope_id=None,
        )

    assert captured_ids == ["bound-only", "collab/shared-model"]
