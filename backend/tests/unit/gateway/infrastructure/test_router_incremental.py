"""Router 增量 add_deployment。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domains.gateway.infrastructure.router_singleton import (
    _try_incremental_router_deployment,
    router_deployment_model_names,
)


@pytest.mark.asyncio
async def test_try_incremental_adds_deployment(db_session: AsyncSession) -> None:
    encoded = "team-abc/openai/gpt-4"
    dep = {"model_name": encoded, "litellm_params": {"model": "openai/gpt-4"}}
    router = MagicMock()
    router.model_list = []
    add_fn = MagicMock()
    router.add_deployment = add_fn

    with (
        patch(
            "domains.gateway.infrastructure.router_singleton._build_deployments_for_encoded_model",
            new=AsyncMock(return_value=[dep]),
        ),
        patch(
            "domains.gateway.infrastructure.router_singleton.get_router_sync",
            return_value=router,
        ),
    ):
        ok = await _try_incremental_router_deployment(db_session, encoded)

    assert ok is True
    add_fn.assert_called_once_with(deployment=dep)


def test_router_deployment_model_names() -> None:
    router = MagicMock(
        model_list=[
            {"model_name": "a"},
            {"model_name": "b"},
            {"not_model_name": "skip"},
        ]
    )
    names = router_deployment_model_names(router)
    assert names == frozenset({"a", "b"})
