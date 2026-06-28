"""model_selector_reads 团队作用域回退。"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
import uuid

import pytest

from domains.gateway.application.catalog.model_selector_reads import (
    get_default_for_model_type,
    list_available_system_models,
)
from libs.iam.permission_context import PermissionContext, set_permission_context


@pytest.mark.unit
@pytest.mark.asyncio
async def test_list_available_system_models_falls_back_to_permission_team() -> None:
    team_id = uuid.uuid4()
    set_permission_context(
        PermissionContext(
            user_id=uuid.uuid4(),
            role="user",
            team_id=team_id,
            team_role="owner",
        )
    )
    catalog = AsyncMock()
    catalog.list_visible_models = AsyncMock(return_value=[])

    await list_available_system_models(catalog, model_type="text")

    catalog.list_visible_models.assert_awaited_once_with(
        billing_team_id=team_id,
        model_type="text",
        user_id=None,
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_default_for_model_type_falls_back_to_permission_team() -> None:
    team_id = uuid.uuid4()
    set_permission_context(
        PermissionContext(
            user_id=uuid.uuid4(),
            role="user",
            team_id=team_id,
            team_role="owner",
        )
    )
    catalog = AsyncMock()
    catalog.list_visible_models = AsyncMock(return_value=[])
    catalog.list_personal_models_for_selector = AsyncMock(return_value=[])

    with patch(
        "domains.gateway.application.catalog.model_selector_reads.resolve_scenario_default",
        new_callable=AsyncMock,
        return_value=None,
    ):
        await get_default_for_model_type(catalog, "text")

    catalog.list_visible_models.assert_awaited_once_with(
        billing_team_id=team_id,
        model_type="text",
        user_id=None,
    )
