"""platform budget usage 展示读集成测试。"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal
import types
from typing import Any
import uuid

from httpx import AsyncClient
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.gateway.application.proxy_deferred_tasks import shutdown_proxy_deferred_tasks
from domains.gateway.domain.quota_plan import PLATFORM_NS
from domains.gateway.infrastructure.models.quota_plan_usage_bucket import (
    GatewayQuotaPlanUsageBucket,
)
from domains.gateway.infrastructure.models.request_log import GatewayRequestLog
from domains.gateway.infrastructure.router_singleton import reload_router
from domains.identity.infrastructure.models.user import User
from domains.tenancy.application.team_service import TeamService
from libs.api.paths import openai_compat_base

_OPENAI_CHAT = f"{openai_compat_base()}/chat/completions"

_PROMPT_TOKENS = 80
_COMPLETION_TOKENS = 40
_EXPECTED_TOTAL_TOKENS = _PROMPT_TOKENS + _COMPLETION_TOKENS


def _quota_rule_list_items(body: dict | list) -> list:
    if isinstance(body, list):
        return body
    return body["items"]


@pytest.fixture(autouse=True)
def _bind_platform_settlement_to_test_db(
    monkeypatch: pytest.MonkeyPatch, db_session: AsyncSession
) -> None:
    from domains.gateway.application import budget_usage_persist as persist_mod
    import libs.db.database as db_mod

    @asynccontextmanager
    async def _ctx():
        yield db_session

    monkeypatch.setattr(persist_mod, "get_session_context", _ctx)
    monkeypatch.setattr(db_mod, "get_session_context", _ctx)


async def _run_router_success_callback(router: Any, kw: dict[str, Any], response_obj: Any) -> None:
    """触发 LiteLLM success callback（写日志 + 预算结算）。"""
    import time

    import litellm

    request_id = f"pb-e2e-{uuid.uuid4().hex}"
    metadata = kw.setdefault("metadata", {})
    if isinstance(metadata, dict):
        metadata.setdefault("gateway_request_id", request_id)
    kw.setdefault("litellm_call_id", request_id)
    now = time.time()
    for cb in list(litellm.callbacks or []):
        on_success = getattr(cb, "async_log_success_event", None)
        if on_success is not None:
            await on_success(kw, response_obj, now, now)


def _fake_openai_chat_response(*, model: str) -> Any:
    message = types.SimpleNamespace(content="ok", tool_calls=None)
    choice = types.SimpleNamespace(message=message, finish_reason="stop")
    usage = types.SimpleNamespace(
        prompt_tokens=_PROMPT_TOKENS,
        completion_tokens=_COMPLETION_TOKENS,
        total_tokens=_EXPECTED_TOTAL_TOKENS,
        prompt_tokens_details={},
        completion_tokens_details={},
    )
    return types.SimpleNamespace(
        id="chatcmpl-platform-budget-e2e",
        choices=[choice],
        usage=usage,
        model=model,
        _hidden_params={"response_cost": 0.0},
    )


async def _setup_platform_budget_chat(
    dev_client: AsyncClient,
    auth_headers: dict[str, str],
    db_session: AsyncSession,
    test_user: User,
) -> tuple[uuid.UUID, str, str, uuid.UUID]:
    """返回 (team_id, model_name, plain_key, budget_id)。"""
    from domains.gateway.application.gateway_cache_invalidation import (
        clear_all_gateway_read_caches_for_tests,
    )

    clear_all_gateway_read_caches_for_tests()
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    await db_session.commit()

    r_cred = await dev_client.post(
        f"/api/v1/gateway/teams/{team.id}/credentials",
        headers=auth_headers,
        json={
            "provider": "openai",
            "name": f"pb-e2e-cred-{uuid.uuid4().hex[:8]}",
            "api_key": "sk-platform-budget-e2e-test-key-123456",
            "scope": "team",
        },
    )
    assert r_cred.status_code == 201, r_cred.text
    credential_id = r_cred.json()["id"]

    model_name = f"pb-e2e-{uuid.uuid4().hex[:8]}"
    r_model = await dev_client.post(
        f"/api/v1/gateway/teams/{team.id}/models",
        headers=auth_headers,
        json={
            "name": model_name,
            "capability": "chat",
            "real_model": "openai/gpt-4o-mini",
            "credential_id": credential_id,
            "provider": "openai",
        },
    )
    assert r_model.status_code == 201, r_model.text

    r_budget = await dev_client.put(
        f"/api/v1/gateway/teams/{team.id}/quota-rules/batch",
        headers=auth_headers,
        json={
            "rules": [
                {
                    "layer": "platform",
                    "target_kind": "tenant",
                    "period": "daily",
                    "limit_tokens": 1_000_000,
                }
            ]
        },
    )
    assert r_budget.status_code == 200, r_budget.text
    budget_id = uuid.UUID(r_budget.json()["succeeded"][0]["source_ref"]["budget_id"])

    await reload_router(db_session)

    r_vkey = await dev_client.post(
        f"/api/v1/gateway/teams/{team.id}/keys",
        headers=auth_headers,
        json={"name": f"pb-e2e-vkey-{uuid.uuid4().hex[:8]}"},
    )
    assert r_vkey.status_code == 201, r_vkey.text
    plain_key = r_vkey.json()["plain_key"]

    return team.id, model_name, plain_key, budget_id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_platform_budget_usage_visible_after_redis_flush(
    dev_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """展示读 DB：清空 Redis 预算键后 platform include_usage 仍能从 bucket/日志读到用量。"""
    team_id, model_name, plain_key, budget_id = await _setup_platform_budget_chat(
        dev_client, auth_headers, db_session, test_user
    )
    response_obj = _fake_openai_chat_response(model=model_name)

    async def _patched_acompletion(router_self: Any, **kw: Any) -> Any:
        await _run_router_success_callback(router_self, kw, response_obj)
        return response_obj

    monkeypatch.setattr("litellm.router.Router.acompletion", _patched_acompletion)

    r_chat = await dev_client.post(
        _OPENAI_CHAT,
        headers={"Authorization": f"Bearer {plain_key}"},
        json={
            "model": model_name,
            "messages": [{"role": "user", "content": "platform budget e2e"}],
            "max_tokens": 64,
        },
    )
    assert r_chat.status_code == 200, r_chat.text
    await shutdown_proxy_deferred_tasks()

    log_tokens = (
        await db_session.execute(
            select(
                func.coalesce(
                    func.sum(GatewayRequestLog.input_tokens + GatewayRequestLog.output_tokens),
                    0,
                )
            ).where(
                GatewayRequestLog.tenant_id == team_id,
                GatewayRequestLog.status == "success",
            )
        )
    ).scalar_one()
    assert int(log_tokens) >= _EXPECTED_TOTAL_TOKENS, log_tokens

    from libs.db.redis import get_redis_client

    redis = await get_redis_client()
    async for key in redis.scan_iter("gateway:budget:*"):
        await redis.delete(key)

    r_rules = await dev_client.get(
        f"/api/v1/gateway/teams/{team_id}/quota-rules",
        headers=auth_headers,
        params={"layer": "platform", "include_usage": "true"},
    )
    assert r_rules.status_code == 200, r_rules.text
    rows = _quota_rule_list_items(r_rules.json())
    matched = [
        row
        for row in rows
        if row.get("source_ref", {}).get("budget_id") == str(budget_id)
        and row.get("key", {}).get("period") == "daily"
        and row.get("key", {}).get("model_name") is None
    ]
    assert matched, rows
    usage = matched[0].get("usage")
    assert usage is not None, matched[0]
    assert int(usage["current_tokens"]) >= _EXPECTED_TOTAL_TOKENS, usage


@pytest.mark.integration
@pytest.mark.asyncio
async def test_platform_display_merges_partial_bucket_with_logs(
    dev_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    auth_headers: dict[str, str],
) -> None:
    """部分 bucket 行存在时，展示读应取 bucket 与日志窗口的较大值。"""
    from domains.gateway.application.gateway_cache_invalidation import (
        clear_all_gateway_read_caches_for_tests,
    )

    clear_all_gateway_read_caches_for_tests()
    team = await TeamService(db_session).ensure_personal_team(test_user.id)

    budget_id = uuid.uuid4()
    from domains.gateway.infrastructure.models.budget import GatewayBudget

    db_session.add(
        GatewayBudget(
            id=budget_id,
            target_kind="tenant",
            target_id=team.id,
            period="daily",
            model_name=None,
            limit_tokens=1_000_000,
        )
    )
    await db_session.flush()

    window_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    db_session.add(
        GatewayRequestLog(
            tenant_id=team.id,
            user_id=test_user.id,
            capability="chat",
            status="success",
            input_tokens=_PROMPT_TOKENS,
            output_tokens=_COMPLETION_TOKENS,
            cost_usd=Decimal("0.01"),
            created_at=datetime.now(UTC),
        )
    )
    db_session.add(
        GatewayQuotaPlanUsageBucket(
            ns=PLATFORM_NS,
            plan_id=budget_id,
            quota_id=budget_id,
            window_start=window_start,
            tokens=10,
            requests=1,
            cost_usd=Decimal("0"),
        )
    )
    await db_session.commit()

    r_rules = await dev_client.get(
        f"/api/v1/gateway/teams/{team.id}/quota-rules",
        headers=auth_headers,
        params={"layer": "platform", "include_usage": "true"},
    )
    assert r_rules.status_code == 200, r_rules.text
    matched = [
        row
        for row in _quota_rule_list_items(r_rules.json())
        if row.get("source_ref", {}).get("budget_id") == str(budget_id)
        and row.get("key", {}).get("period") == "daily"
        and row.get("key", {}).get("model_name") is None
    ]
    assert matched, r_rules.json()
    usage = matched[0]["usage"]
    assert int(usage["current_tokens"]) >= _EXPECTED_TOTAL_TOKENS, usage
