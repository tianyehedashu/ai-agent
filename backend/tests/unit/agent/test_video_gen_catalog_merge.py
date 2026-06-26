"""video_gen_catalog：合并系统与个人视频模型。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest

from domains.agent.application.video_gen_catalog import list_merged_video_models


@pytest.mark.asyncio
async def test_list_merged_video_models_includes_personal_models() -> None:
    user_id = uuid.uuid4()
    session = MagicMock()
    system_item = {
        "id": "team-video-model",
        "display_name": "Team Video",
        "capabilities": {"max_reference_images": 4},
        "video_durations": [5, 10],
    }
    personal_item = {
        "id": str(uuid.uuid4()),
        "display_name": "My Video",
        "capabilities": {"max_reference_images": 2},
        "video_durations": [5],
    }

    with (
        patch(
            "domains.gateway.application.sql_model_catalog.get_model_catalog_adapter",
            return_value=MagicMock(),
        ),
        patch(
            "domains.gateway.application.internal_bridge_actor.resolve_internal_gateway_team_id",
            return_value=uuid.uuid4(),
        ),
        patch(
            "domains.gateway.application.model_selector_reads.list_available_system_models",
            new=AsyncMock(return_value=[system_item]),
        ),
        patch(
            "domains.gateway.application.model_selector_reads.list_personal_models_for_selector",
            new=AsyncMock(return_value=[personal_item]),
        ),
    ):
        merged = await list_merged_video_models(session, user_id=user_id)

    values = {item["value"] for item in merged}
    assert system_item["id"] in values
    assert personal_item["id"] in values
