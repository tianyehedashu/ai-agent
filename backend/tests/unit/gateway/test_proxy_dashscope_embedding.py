"""ProxyUseCase.embedding：DashScope 走 OpenAI 兼容直连，不经 Router.aembedding。"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domains.gateway.application.proxy_use_case import ProxyContext, ProxyUseCase
from domains.gateway.domain.types import GatewayCapability, VirtualKeyPrincipal
from domains.gateway.infrastructure.repositories.model_repository import GatewayModelRepository
from tests.unit.gateway.test_management_test_model import _seed_team_credential_and_model


def _vkey(team_id: uuid.UUID) -> VirtualKeyPrincipal:
    return VirtualKeyPrincipal(
        vkey_id=uuid.uuid4(),
        vkey_name="test",
        team_id=team_id,
        user_id=uuid.uuid4(),
        allowed_models=(),
        allowed_capabilities=(),
        rpm_limit=None,
        tpm_limit=None,
        store_full_messages=False,
        guardrail_enabled=False,
        is_system=False,
    )


class _NoopBudget:
    async def check_rate_limit(self, **_kwargs: object) -> None:
        return None

    async def check_budget(self, **_kwargs: object) -> Any:
        from domains.gateway.application.budget_service import BudgetCheckResult

        return BudgetCheckResult(allowed=True)

    async def reserve(self, **_kwargs: object) -> None:
        return None

    async def release(self, **_kwargs: object) -> None:
        return None

    async def commit(self, **_kwargs: object) -> None:
        return None


@pytest.mark.asyncio
async def test_embedding_dashscope_uses_compatible_api(
    db_session: AsyncSession,
    test_user: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    team_id, model_id = await _seed_team_credential_and_model(
        db_session,
        test_user,
        capability="embedding",
        real_model="text-embedding-v3",
        provider="dashscope",
    )
    model_row = await GatewayModelRepository(db_session).get(model_id)
    assert model_row is not None
    client_model = model_row.name

    fake_response = {
        "object": "list",
        "data": [{"object": "embedding", "embedding": [0.1, 0.2], "index": 0}],
        "model": "text-embedding-v3",
        "usage": {"prompt_tokens": 1, "total_tokens": 1},
    }
    perform_mock = AsyncMock(return_value=fake_response)

    async def router_should_not_run(**_kwargs: object) -> None:
        raise AssertionError("router.aembedding must not be called for dashscope")

    ctx = ProxyContext(
        team_id=team_id,
        user_id=test_user.id,
        vkey=_vkey(team_id),
        capability=GatewayCapability.EMBEDDING,
        request_id="req-embed",
        store_full_messages=False,
        guardrail_enabled=False,
    )
    use_case = ProxyUseCase(db_session, budget_service=_NoopBudget())
    monkeypatch.setattr(
        "domains.gateway.application.proxy_litellm_client.perform_dashscope_embedding",
        perform_mock,
    )
    with patch(
        "domains.gateway.infrastructure.router_singleton.get_router",
        new=AsyncMock(side_effect=router_should_not_run),
    ):
        result = await use_case.embedding(
            ctx,
            {"model": client_model, "input": ["ping"]},
        )

    assert result["data"][0]["embedding"] == [0.1, 0.2]
    perform_mock.assert_awaited_once()
    req = perform_mock.await_args.args[0]
    assert req.json_body["model"] == "text-embedding-v3"
    assert "/embeddings" in req.url