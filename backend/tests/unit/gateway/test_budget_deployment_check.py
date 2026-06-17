"""Phase2 成员+凭据预算预扣单测（pre_call hook 内联逻辑）。"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from domains.gateway.application.budget_config_cache import BudgetConfigRow
import domains.gateway.application.budget_deployment_check as mod
from domains.gateway.application.budget_service import BudgetCheckResult
from domains.gateway.domain.errors import BudgetExceededError

_MODEL = "gpt-4--abc"


def _data(user_id: uuid.UUID, cred_id: uuid.UUID, *, scope: str | None = None) -> dict[str, Any]:
    model_info: dict[str, Any] = {
        "gateway_credential_id": str(cred_id),
        "gateway_model_name": _MODEL,
    }
    if scope is not None:
        model_info["gateway_credential_scope"] = scope
    return {
        "metadata": {"gateway_user_id": str(user_id)},
        "litellm_params": {"model_info": model_info},
    }


def _config(cred_id: uuid.UUID, **limits: object) -> BudgetConfigRow:
    return BudgetConfigRow(
        target_kind="user",
        target_id=uuid.uuid4(),
        period="monthly",
        model_name=_MODEL,
        limit_usd=limits.get("limit_usd"),  # type: ignore[arg-type]
        limit_tokens=limits.get("limit_tokens"),  # type: ignore[arg-type]
        limit_requests=limits.get("limit_requests"),  # type: ignore[arg-type]
        credential_id=cred_id,
    )


def _coord_dict(user_id: uuid.UUID, cred_id: uuid.UUID, config: BudgetConfigRow) -> dict[Any, Any]:
    return {("user", user_id, "monthly", _MODEL, cred_id, None): config}


def _patch_service(monkeypatch, *, check_result: BudgetCheckResult) -> MagicMock:
    svc = MagicMock()
    svc.read_budget_usage_batch = AsyncMock(return_value={})
    svc.check_budget = AsyncMock(return_value=check_result)
    svc.reserve = AsyncMock(return_value=(1, 0))
    svc.release = AsyncMock()
    monkeypatch.setattr(mod, "BudgetService", lambda: svc)
    return svc


@pytest.mark.asyncio
async def test_skips_without_attribution(monkeypatch) -> None:
    monkeypatch.setattr(mod, "has_user_credential", AsyncMock(return_value=True))
    cached = AsyncMock()
    monkeypatch.setattr(mod, "get_cached_budget_by_plan", cached)

    await mod.maybe_reserve_user_credential_budget({"metadata": {}})

    cached.assert_not_awaited()


@pytest.mark.asyncio
async def test_byok_scope_user_skipped(monkeypatch) -> None:
    has = AsyncMock(return_value=True)
    monkeypatch.setattr(mod, "has_user_credential", has)

    await mod.maybe_reserve_user_credential_budget(
        _data(uuid.uuid4(), uuid.uuid4(), scope="user")
    )

    has.assert_not_awaited()


@pytest.mark.asyncio
async def test_no_rule_fast_path(monkeypatch) -> None:
    monkeypatch.setattr(mod, "has_user_credential", AsyncMock(return_value=False))
    cached = AsyncMock()
    monkeypatch.setattr(mod, "get_cached_budget_by_plan", cached)

    data = _data(uuid.uuid4(), uuid.uuid4())
    await mod.maybe_reserve_user_credential_budget(data)

    cached.assert_not_awaited()
    assert mod._RESERVATIONS_META_KEY not in data["metadata"]


@pytest.mark.asyncio
async def test_reserves_and_records_metadata(monkeypatch) -> None:
    user_id, cred_id = uuid.uuid4(), uuid.uuid4()
    monkeypatch.setattr(mod, "has_user_credential", AsyncMock(return_value=True))
    config = _config(cred_id, limit_requests=10)
    monkeypatch.setattr(
        mod,
        "get_cached_budget_by_plan",
        AsyncMock(return_value=_coord_dict(user_id, cred_id, config)),
    )
    svc = _patch_service(monkeypatch, check_result=BudgetCheckResult(allowed=True))

    data = _data(user_id, cred_id)
    await mod.maybe_reserve_user_credential_budget(data, estimate_tokens=0)

    svc.reserve.assert_awaited_once()
    reservations = data["metadata"][mod._RESERVATIONS_META_KEY]
    assert len(reservations) == 1
    assert reservations[0]["credential_id"] == str(cred_id)


@pytest.mark.asyncio
async def test_exhausted_raises_and_releases(monkeypatch) -> None:
    user_id, cred_id = uuid.uuid4(), uuid.uuid4()
    monkeypatch.setattr(mod, "has_user_credential", AsyncMock(return_value=True))
    config = _config(cred_id, limit_usd=Decimal("50"))
    monkeypatch.setattr(
        mod,
        "get_cached_budget_by_plan",
        AsyncMock(return_value=_coord_dict(user_id, cred_id, config)),
    )
    svc = _patch_service(
        monkeypatch,
        check_result=BudgetCheckResult(allowed=False, reason="usd", used_usd=Decimal("60")),
    )

    data = _data(user_id, cred_id)
    with pytest.raises(BudgetExceededError) as exc:
        await mod.maybe_reserve_user_credential_budget(data)

    assert exc.value.scope == "user_credential"
    svc.reserve.assert_not_awaited()
    assert mod._RESERVATIONS_META_KEY not in data["metadata"]


@pytest.mark.asyncio
async def test_success_callback_releases_only_token_reservations(monkeypatch) -> None:
    _patch_service(monkeypatch, check_result=BudgetCheckResult(allowed=True))
    svc = mod.BudgetService()
    metadata = {
        mod._RESERVATIONS_META_KEY: [
            {
                "target_id": str(uuid.uuid4()),
                "period": "monthly",
                "budget_model_name": _MODEL,
                "credential_id": str(uuid.uuid4()),
                "reserved_requests": 1,
                "reserved_tokens": 35,
            }
        ]
    }

    await mod.release_user_credential_budget_token_reservations_from_metadata(metadata)

    svc.release.assert_awaited_once()
    kwargs = svc.release.await_args.kwargs
    assert kwargs["reserved_requests"] == 0
    assert kwargs["reserved_tokens"] == 35
