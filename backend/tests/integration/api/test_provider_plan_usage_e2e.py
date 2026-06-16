"""ProviderPlan 上游配额：代理调用后 token 写入 Redis 并在配额中心可见。"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
import time
import types
from typing import Any
import uuid

from contextlib import asynccontextmanager

from httpx import AsyncClient
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bootstrap.main import app
from domains.gateway.application.proxy_deferred_tasks import shutdown_proxy_deferred_tasks
from domains.gateway.domain.quota_plan import PROVIDER_NS
from domains.gateway.domain.types import VirtualKeyPrincipal
from domains.gateway.infrastructure.models.quota_plan_usage_bucket import (
    GatewayQuotaPlanUsageBucket,
)
from domains.gateway.infrastructure.models.request_log import GatewayRequestLog
from domains.gateway.infrastructure.router_singleton import reload_router
from domains.gateway.presentation.deps import (
    VkeyOrApikeyPrincipal,
    bearer_vkey_or_apikey_auth,
)
from domains.identity.infrastructure.models.user import User
from domains.tenancy.application.team_service import TeamService
from libs.api.paths import openai_compat_base

_OPENAI_CHAT = f"{openai_compat_base()}/chat/completions"

_PROMPT_TOKENS = 100
_COMPLETION_TOKENS = 50
_EXPECTED_TOTAL_TOKENS = _PROMPT_TOKENS + _COMPLETION_TOKENS


@pytest.fixture(autouse=True)
def _bind_plan_settlement_to_test_db_session(
    monkeypatch: pytest.MonkeyPatch, db_session: AsyncSession
) -> None:
    """ProviderPlan 结算/加载与 HTTP 写入共用同一 integration session。"""
    from domains.gateway.application import provider_plan_callback_settlement as provider_cb
    from domains.gateway.application import provider_plan_guard as provider_guard_mod

    @asynccontextmanager
    async def _ctx():
        yield db_session

    for mod in (provider_guard_mod, provider_cb):
        monkeypatch.setattr(mod, "get_session_context", _ctx)


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
        id="chatcmpl-provider-plan-e2e",
        choices=[choice],
        usage=usage,
        model=model,
        _hidden_params={"response_cost": 0.0},
    )


async def _merge_router_deployment(router: Any, kw: dict[str, Any]) -> None:
    """LiteLLM Router 在 pre_call 前会把选中 deployment 的 model_info 并入 kwargs。"""
    model = kw.get("model")
    if not isinstance(model, str):
        return
    for deployment in getattr(router, "model_list", []) or []:
        if deployment.get("model_name") != model:
            continue
        litellm_params = deployment.get("litellm_params")
        model_info = deployment.get("model_info")
        if not isinstance(litellm_params, dict):
            return
        target = kw.setdefault("litellm_params", {})
        if not isinstance(target, dict):
            return
        for key, value in litellm_params.items():
            if key not in target:
                target[key] = value
        if isinstance(model_info, dict):
            existing_mi = target.get("model_info")
            if isinstance(existing_mi, dict):
                target["model_info"] = {**existing_mi, **model_info}
            else:
                target["model_info"] = dict(model_info)
        return


async def _run_router_hooks(router: Any, kw: dict[str, Any], response_obj: Any) -> None:
    """模拟 LiteLLM Router：pre_call（ProviderPlan 打标）→ success callback（结算）。"""
    import litellm

    await _merge_router_deployment(router, kw)
    request_id = f"pp-e2e-{uuid.uuid4().hex}"
    metadata = kw.setdefault("metadata", {})
    if isinstance(metadata, dict):
        metadata.setdefault("gateway_request_id", request_id)
    kw.setdefault("litellm_call_id", request_id)
    now = time.time()
    for cb in list(litellm.callbacks or []):
        pre_call = getattr(cb, "async_pre_call_hook", None)
        if pre_call is not None:
            await pre_call(None, None, kw, "completion")
    for cb in list(litellm.callbacks or []):
        on_success = getattr(cb, "async_log_success_event", None)
        if on_success is not None:
            await on_success(kw, response_obj, now, now)


async def _setup_team_model_plan_vkey(
    dev_client: AsyncClient,
    auth_headers: dict[str, str],
    db_session: AsyncSession,
    test_user: User,
) -> tuple[uuid.UUID, str, str, str, uuid.UUID]:
    """返回 (team_id, credential_id, model_name, vkey_plain, plan_id)。"""
    from domains.gateway.application.gateway_cache_invalidation import (
        clear_all_gateway_read_caches_for_tests,
    )

    clear_all_gateway_read_caches_for_tests()
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    await db_session.commit()
    now = datetime.now(UTC).replace(microsecond=0)
    real_model = "openai/gpt-4o-mini"

    r_cred = await dev_client.post(
        f"/api/v1/gateway/teams/{team.id}/credentials",
        headers=auth_headers,
        json={
            "provider": "openai",
            "name": f"pp-e2e-cred-{uuid.uuid4().hex[:8]}",
            "api_key": "sk-provider-plan-e2e-test-key-123456",
            "scope": "team",
        },
    )
    assert r_cred.status_code == 201, r_cred.text
    credential_id = r_cred.json()["id"]

    model_name = f"pp-e2e-{uuid.uuid4().hex[:8]}"
    r_model = await dev_client.post(
        f"/api/v1/gateway/teams/{team.id}/models",
        headers=auth_headers,
        json={
            "name": model_name,
            "capability": "chat",
            "real_model": real_model,
            "credential_id": credential_id,
            "provider": "openai",
        },
    )
    assert r_model.status_code == 201, r_model.text

    r_plan = await dev_client.post(
        f"/api/v1/gateway/teams/{team.id}/credentials/{credential_id}/provider-plans",
        headers=auth_headers,
        json={
            "real_model": real_model,
            "label": "e2e-pack",
            "valid_from": (now - timedelta(minutes=1)).isoformat(),
            "valid_until": (now + timedelta(days=30)).isoformat(),
            "quotas": [
                {
                    "label": "daily",
                    "window_seconds": 86400,
                    "reset_strategy": "calendar_daily_utc",
                    "limit_tokens": 1_000_000,
                }
            ],
        },
    )
    assert r_plan.status_code == 201, r_plan.text
    plan_id = uuid.UUID(r_plan.json()["id"])

    await reload_router(db_session)

    r_vkey = await dev_client.post(
        f"/api/v1/gateway/teams/{team.id}/keys",
        headers=auth_headers,
        json={"name": f"pp-e2e-vkey-{uuid.uuid4().hex[:8]}"},
    )
    assert r_vkey.status_code == 201, r_vkey.text
    plain_key = r_vkey.json()["plain_key"]

    return team.id, credential_id, model_name, plain_key, plan_id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_provider_plan_token_usage_after_openai_compat_chat(
    dev_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OpenAI 兼容 chat 成功后：请求日志有 token，配额中心 upstream 已用 token 同步增加。"""
    team_id, credential_id, model_name, plain_key, plan_id = await _setup_team_model_plan_vkey(
        dev_client, auth_headers, db_session, test_user
    )
    response_obj = _fake_openai_chat_response(model=model_name)

    async def _patched_acompletion(router_self: Any, **kw: Any) -> Any:
        await _run_router_hooks(router_self, kw, response_obj)
        return response_obj

    monkeypatch.setattr("litellm.router.Router.acompletion", _patched_acompletion)

    r_chat = await dev_client.post(
        _OPENAI_CHAT,
        headers={"Authorization": f"Bearer {plain_key}"},
        json={
            "model": model_name,
            "messages": [{"role": "user", "content": "quota e2e"}],
            "max_tokens": 64,
        },
    )
    assert r_chat.status_code == 200, r_chat.text
    await shutdown_proxy_deferred_tasks()

    stmt = (
        select(GatewayRequestLog)
        .where(GatewayRequestLog.tenant_id == team_id)
        .order_by(GatewayRequestLog.created_at.desc())
    )
    log_row = (await db_session.execute(stmt)).scalars().first()
    assert log_row is not None, "调用统计应写入 gateway_request_logs"
    assert log_row.input_tokens == _PROMPT_TOKENS, log_row.input_tokens
    assert log_row.output_tokens == _COMPLETION_TOKENS, log_row.output_tokens
    assert log_row.provider_plan_id == plan_id, log_row.provider_plan_id

    r_rules = await dev_client.get(
        f"/api/v1/gateway/teams/{team_id}/quota-rules",
        headers=auth_headers,
        params={
            "layer": "upstream",
            "credential_id": credential_id,
            "include_usage": "true",
        },
    )
    assert r_rules.status_code == 200, r_rules.text
    rows = r_rules.json()
    matched = [
        row
        for row in rows
        if row.get("source_ref", {}).get("plan_id") == str(plan_id)
        and row.get("key", {}).get("quota_label") == "daily"
    ]
    assert matched, rows
    usage = matched[0].get("usage")
    assert usage is not None, matched[0]
    assert int(usage["current_tokens"]) == _EXPECTED_TOTAL_TOKENS, usage


@pytest.mark.integration
@pytest.mark.asyncio
async def test_provider_plan_callback_persists_usage_bucket(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """callback 结算后汇总表应写入窗口用量。"""
    from decimal import Decimal
    from unittest.mock import AsyncMock

    from domains.gateway.application import quota_plan_usage_persist as persist_mod
    from domains.gateway.domain.quota_plan import PlanQuotaSpec

    plan_id = uuid.uuid4()
    quota_id = uuid.uuid4()
    spec = PlanQuotaSpec(
        quota_id=quota_id,
        label="daily",
        window_seconds=86400,
        reset_strategy="calendar_daily_utc",
        limit_tokens=1_000_000,
    )

    monkeypatch.setattr(persist_mod, "_acquire_bucket_upsert_once", AsyncMock(return_value=True))

    @asynccontextmanager
    async def _test_session_context():
        yield db_session

    monkeypatch.setattr(persist_mod, "get_session_context", _test_session_context)

    settled_at = datetime.now(UTC)
    await persist_mod._upsert_quota_plan_usage(
        ns=PROVIDER_NS,
        plan_id=plan_id,
        specs=[spec],
        delta_tokens=_EXPECTED_TOTAL_TOKENS,
        delta_cost_usd=Decimal("0.01"),
        delta_requests=1,
        request_id="req-bucket-e2e",
        settled_at=settled_at,
    )
    await db_session.flush()

    bucket_tokens = (
        await db_session.execute(
            select(func.coalesce(func.sum(GatewayQuotaPlanUsageBucket.tokens), 0)).where(
                GatewayQuotaPlanUsageBucket.ns == PROVIDER_NS,
                GatewayQuotaPlanUsageBucket.plan_id == plan_id,
            )
        )
    ).scalar_one()
    assert int(bucket_tokens) == _EXPECTED_TOTAL_TOKENS, bucket_tokens


@pytest.mark.integration
@pytest.mark.asyncio
async def test_provider_plan_usage_visible_after_redis_flush(
    dev_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """展示读 DB：清空 Redis 配额键后 include_usage 仍能从日志/汇总表读到用量。"""
    team_id, credential_id, model_name, plain_key, plan_id = await _setup_team_model_plan_vkey(
        dev_client, auth_headers, db_session, test_user
    )
    response_obj = _fake_openai_chat_response(model=model_name)

    async def _patched_acompletion(router_self: Any, **kw: Any) -> Any:
        await _run_router_hooks(router_self, kw, response_obj)
        return response_obj

    monkeypatch.setattr("litellm.router.Router.acompletion", _patched_acompletion)

    r_chat = await dev_client.post(
        _OPENAI_CHAT,
        headers={"Authorization": f"Bearer {plain_key}"},
        json={
            "model": model_name,
            "messages": [{"role": "user", "content": "redis flush e2e"}],
            "max_tokens": 64,
        },
    )
    assert r_chat.status_code == 200, r_chat.text
    await shutdown_proxy_deferred_tasks()

    from libs.db.redis import get_redis_client

    redis = await get_redis_client()
    async for key in redis.scan_iter("gateway:quota:provider:*"):
        await redis.delete(key)

    r_rules = await dev_client.get(
        f"/api/v1/gateway/teams/{team_id}/quota-rules",
        headers=auth_headers,
        params={
            "layer": "upstream",
            "credential_id": credential_id,
            "include_usage": "true",
        },
    )
    assert r_rules.status_code == 200, r_rules.text
    rows = r_rules.json()
    matched = [
        row
        for row in rows
        if row.get("source_ref", {}).get("plan_id") == str(plan_id)
        and row.get("key", {}).get("quota_label") == "daily"
    ]
    assert matched, rows
    usage = matched[0].get("usage")
    assert usage is not None, matched[0]
    assert int(usage["current_tokens"]) == _EXPECTED_TOTAL_TOKENS, usage


@pytest.mark.integration
@pytest.mark.asyncio
async def test_provider_plan_precall_stamps_metadata_seen_by_callback(
    dev_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """pre_call 写入的 gateway_provider_plan_id 应出现在 success callback 的 metadata 中。"""
    team_id, _credential_id, model_name, plain_key, plan_id = await _setup_team_model_plan_vkey(
        dev_client, auth_headers, db_session, test_user
    )
    response_obj = _fake_openai_chat_response(model=model_name)
    seen_plan_ids: list[uuid.UUID | None] = []

    principal = VkeyOrApikeyPrincipal(
        via="vkey",
        user_id=test_user.id,
        team_id=team_id,
        vkey=VirtualKeyPrincipal(
            vkey_id=uuid.uuid4(),
            vkey_name="pp-e2e-metadata",
            team_id=team_id,
            user_id=test_user.id,
            allowed_models=(),
            allowed_capabilities=(),
            rpm_limit=None,
            tpm_limit=None,
            store_full_messages=False,
            guardrail_enabled=False,
            is_system=False,
        ),
        platform_api_key_id=None,
        api_key_grant=None,
    )

    async def _patched_acompletion(router_self: Any, **kw: Any) -> Any:
        import litellm

        await _merge_router_deployment(router_self, kw)
        for cb in list(litellm.callbacks or []):
            pre_call = getattr(cb, "async_pre_call_hook", None)
            if pre_call is not None:
                await pre_call(None, None, kw, "completion")
        from domains.gateway.infrastructure.callbacks.cost_calculation import (
            extract_gateway_metadata,
        )

        meta = extract_gateway_metadata(kw)
        raw = meta.get("gateway_provider_plan_id")
        seen_plan_ids.append(uuid.UUID(str(raw)) if raw else None)
        now = time.time()
        for cb in list(litellm.callbacks or []):
            on_success = getattr(cb, "async_log_success_event", None)
            if on_success is not None:
                await on_success(kw, response_obj, now, now)
        return response_obj

    monkeypatch.setattr("litellm.router.Router.acompletion", _patched_acompletion)
    app.dependency_overrides[bearer_vkey_or_apikey_auth] = lambda: principal

    try:
        r_chat = await dev_client.post(
            _OPENAI_CHAT,
            headers={"Authorization": f"Bearer {plain_key}"},
            json={
                "model": model_name,
                "messages": [{"role": "user", "content": "metadata e2e"}],
            },
        )
    finally:
        app.dependency_overrides.pop(bearer_vkey_or_apikey_auth, None)

    assert r_chat.status_code == 200, r_chat.text
    await shutdown_proxy_deferred_tasks()
    assert seen_plan_ids == [plan_id]
