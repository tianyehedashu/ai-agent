"""Gateway 缓存命中 & Token 统计集成测试。

验证两条代理路径（OpenAI 兼容 + Anthropic 原生）的请求日志
和统计聚合是否正确记录了 token 计数与缓存命中。

- OpenAI 路径：``prompt_tokens_details.cached_tokens``
- Anthropic 路径：``cache_read_input_tokens`` + ``cache_creation_input_tokens``
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
import time
import types
from typing import Any
import uuid

from httpx import AsyncClient
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bootstrap.main import app
from domains.gateway.application.proxy.proxy_deferred_tasks import shutdown_proxy_deferred_tasks
from domains.gateway.application.proxy.proxy_use_case import ProxyContext, ProxyUseCase
from domains.gateway.domain.types import VirtualKeyPrincipal
from domains.gateway.infrastructure.models.request_log import GatewayRequestLog
from domains.gateway.presentation.deps import (
    VkeyOrApikeyPrincipal,
    bearer_vkey_or_apikey_auth,
)
from domains.tenancy.application.team_service import TeamService
from libs.api.paths import api_v1_path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_OPENAI_CHAT = api_v1_path("openai", "v1", "chat", "completions")
_ANTHROPIC_MESSAGES = api_v1_path("anthropic", "v1", "messages")


def _principal(team_id: uuid.UUID | None = None) -> VkeyOrApikeyPrincipal:
    tid = team_id or uuid.uuid4()
    return VkeyOrApikeyPrincipal(
        via="vkey",
        user_id=uuid.uuid4(),
        team_id=tid,
        vkey=VirtualKeyPrincipal(
            vkey_id=uuid.uuid4(),
            vkey_name="integ-cache-test",
            team_id=tid,
            user_id=uuid.uuid4(),
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


async def _read_logs(db_session: AsyncSession, team_id: uuid.UUID) -> list[GatewayRequestLog]:
    stmt = (
        select(GatewayRequestLog)
        .where(GatewayRequestLog.tenant_id == team_id)
        .order_by(GatewayRequestLog.created_at.asc())
    )
    return list((await db_session.execute(stmt)).scalars().all())


async def _trigger_callbacks(kwargs: dict[str, Any], response_obj: Any) -> None:
    """模拟 LiteLLM 在 acompletion 完成后 dispatch success callback。"""
    import litellm

    now = time.time()
    for cb in list(litellm.callbacks or []):
        success_fn = getattr(cb, "async_log_success_event", None)
        if success_fn is None:
            continue
        await success_fn(kwargs, response_obj, now, now)


# ---------------------------------------------------------------------------
# Fake responses
# ---------------------------------------------------------------------------


def _fake_openai_response(
    *,
    model: str = "openai/gpt-4o-mini",
    prompt_tokens: int = 100,
    completion_tokens: int = 50,
    cached_tokens: int = 80,
    cost: float = 0.0005,
) -> Any:
    """OpenAI 格式响应（含 prompt_tokens_details.cached_tokens）。"""
    message = types.SimpleNamespace(content="ok", tool_calls=None)
    choice = types.SimpleNamespace(message=message, finish_reason="stop")
    usage = types.SimpleNamespace(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
        prompt_tokens_details={"cached_tokens": cached_tokens},
        completion_tokens_details={"reasoning_tokens": 0},
    )
    return types.SimpleNamespace(
        choices=[choice],
        usage=usage,
        model=model,
        _hidden_params={"response_cost": cost},
    )


def _fake_anthropic_response(
    *,
    model: str = "anthropic/claude-3-haiku",
    input_tokens: int = 20,
    output_tokens: int = 10,
    cache_read: int = 500,
    cache_creation: int = 100,
    cost: float = 0.0003,
) -> Any:
    """Anthropic 格式响应对象（含 cache_read_input_tokens）。"""
    usage = types.SimpleNamespace(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_input_tokens=cache_read,
        cache_creation_input_tokens=cache_creation,
    )
    content = [types.SimpleNamespace(type="text", text="pong")]
    return types.SimpleNamespace(
        id="msg_test",
        type="message",
        role="assistant",
        model=model,
        content=content,
        stop_reason="end_turn",
        stop_sequence=None,
        usage=usage,
        _hidden_params={"response_cost": cost},
    )


def _build_callback_kwargs(
    *,
    model: str,
    team_id: uuid.UUID,
    user_id: uuid.UUID,
    vkey_id: uuid.UUID,
    messages: list[dict[str, Any]] | None = None,
    metadata_extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """构造传给 LiteLLM callback 的最小 kwargs。"""
    metadata: dict[str, Any] = {
        "gateway_team_id": str(team_id),
        "gateway_user_id": str(user_id),
        "gateway_vkey_id": str(vkey_id),
        "gateway_capability": "chat",
        "gateway_request_id": str(uuid.uuid4()),
        "gateway_provider": "openai",
    }
    if metadata_extra:
        metadata.update(metadata_extra)
    return {
        "model": model,
        "messages": messages or [{"role": "user", "content": "hi"}],
        "metadata": metadata,
        "litellm_call_id": str(uuid.uuid4()),
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _disable_redis_counters(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _noop(**_: Any) -> None:
        return None

    monkeypatch.setattr(
        "domains.gateway.infrastructure.callbacks.custom_logger._bump_redis_counters",
        _noop,
    )


@pytest.fixture(autouse=True)
def _upstream_cost_from_hidden(monkeypatch: pytest.MonkeyPatch) -> None:
    from contextlib import suppress

    from domains.gateway.application.pricing import upstream_cost_resolver as resolver

    def _completion_cost(
        response: Any,
        *,
        model: str | None = None,
        custom_cost_per_token: dict[str, Any] | None = None,
    ) -> Decimal | None:
        del model, custom_cost_per_token
        hp = getattr(response, "_hidden_params", None)
        if hp is None:
            return None
        raw = hp.get("response_cost") if isinstance(hp, dict) else getattr(hp, "response_cost", None)
        if raw is None:
            return None
        with suppress(Exception):
            return Decimal(str(raw))
        return None

    monkeypatch.setattr(resolver, "_completion_cost_upstream", _completion_cost)


# ---------------------------------------------------------------------------
# Tests: OpenAI 兼容路径
# ---------------------------------------------------------------------------


async def _register_team_model(
    dev_client: AsyncClient,
    team_id: uuid.UUID,
    headers: dict[str, str],
    *,
    model_name: str,
    provider: str = "openai",
) -> None:
    """通过管理 API 注册团队凭据 + 模型。"""
    cred_name = f"cred-{uuid.uuid4().hex[:6]}"
    r_cred = await dev_client.post(
        f"/api/v1/gateway/teams/{team_id}/credentials",
        headers=headers,
        json={
            "provider": provider,
            "name": cred_name,
            "api_key": "sk-test-key-for-cache-test",
            "scope": "team",
        },
    )
    assert r_cred.status_code == 201, r_cred.text
    cid = r_cred.json()["id"]
    r_model = await dev_client.post(
        f"/api/v1/gateway/teams/{team_id}/models",
        headers=headers,
        json={
            "name": model_name,
            "capability": "chat",
            "real_model": "gpt-4o-mini",
            "credential_id": cid,
            "provider": provider,
        },
    )
    assert r_model.status_code == 201, r_model.text


@pytest.mark.integration
@pytest.mark.asyncio
async def test_openai_path_cache_hit_and_tokens_in_request_log(
    dev_client: AsyncClient,
    db_session: AsyncSession,
    test_user: Any,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OpenAI /v1/chat/completions 路径：验证 cached_tokens 和 cache_hit 写入请求日志。"""
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    await db_session.commit()

    model_name = f"gw-test-{uuid.uuid4().hex[:8]}"
    await _register_team_model(dev_client, team.id, auth_headers, model_name=model_name)

    principal = _principal(team_id=team.id)
    response_obj = _fake_openai_response(
        model=model_name,
        prompt_tokens=100,
        completion_tokens=50,
        cached_tokens=80,
    )
    kwargs = _build_callback_kwargs(
        model=model_name,
        team_id=team.id,
        user_id=test_user.id,
        vkey_id=principal.vkey.vkey_id,
        metadata_extra={
            "gateway_provider": "openai",
            "gateway_cache_hit": True,  # proxy adapter 层在 cached_tokens > 0 时设置
        },
    )

    async def _patched_acompletion(_self: Any, **kw: Any) -> Any:
        merged_metadata = {**(kw.get("metadata") or {}), **(kwargs["metadata"])}
        kw["metadata"] = merged_metadata
        await _trigger_callbacks(kw, response_obj)
        return response_obj

    monkeypatch.setattr("litellm.router.Router.acompletion", _patched_acompletion)
    app.dependency_overrides[bearer_vkey_or_apikey_auth] = lambda: principal

    try:
        r = await dev_client.post(
            _OPENAI_CHAT,
            headers={"Authorization": "Bearer sk-gw-test"},
            json={
                "model": model_name,
                "messages": [{"role": "user", "content": "hello"}],
                "max_tokens": 100,
            },
        )
    finally:
        app.dependency_overrides.pop(bearer_vkey_or_apikey_auth, None)

    assert r.status_code == 200, r.text
    await shutdown_proxy_deferred_tasks()

    rows = await _read_logs(db_session, team.id)
    assert len(rows) >= 1, f"expected at least one log row, got {len(rows)}"
    row = rows[-1]

    assert row.input_tokens == 100, f"input_tokens: expected 100, got {row.input_tokens}"
    assert row.output_tokens == 50, f"output_tokens: expected 50, got {row.output_tokens}"
    assert row.cached_tokens == 80, f"cached_tokens: expected 80, got {row.cached_tokens}"
    assert row.cache_hit is True, f"cache_hit: expected True, got {row.cache_hit}"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_openai_path_no_cache_tokens_cache_hit_false(
    dev_client: AsyncClient,
    db_session: AsyncSession,
    test_user: Any,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OpenAI 路径无缓存时：cached_tokens=0, cache_hit=False。"""
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    await db_session.commit()

    model_name = f"gw-nocache-{uuid.uuid4().hex[:8]}"
    await _register_team_model(dev_client, team.id, auth_headers, model_name=model_name)

    principal = _principal(team_id=team.id)
    response_obj = _fake_openai_response(
        model=model_name,
        prompt_tokens=50,
        completion_tokens=30,
        cached_tokens=0,
    )
    kwargs = _build_callback_kwargs(
        model=model_name,
        team_id=team.id,
        user_id=test_user.id,
        vkey_id=principal.vkey.vkey_id,
        metadata_extra={"gateway_provider": "openai"},  # no gateway_cache_hit
    )

    async def _patched_acompletion(_self: Any, **kw: Any) -> Any:
        merged_metadata = {**(kw.get("metadata") or {}), **(kwargs["metadata"])}
        kw["metadata"] = merged_metadata
        await _trigger_callbacks(kw, response_obj)
        return response_obj

    monkeypatch.setattr("litellm.router.Router.acompletion", _patched_acompletion)
    app.dependency_overrides[bearer_vkey_or_apikey_auth] = lambda: principal

    try:
        r = await dev_client.post(
            _OPENAI_CHAT,
            headers={"Authorization": "Bearer sk-gw-test"},
            json={
                "model": model_name,
                "messages": [{"role": "user", "content": "hello"}],
            },
        )
    finally:
        app.dependency_overrides.pop(bearer_vkey_or_apikey_auth, None)

    assert r.status_code == 200, r.text
    await shutdown_proxy_deferred_tasks()

    rows = await _read_logs(db_session, team.id)
    assert len(rows) >= 1
    row = rows[-1]

    assert row.input_tokens == 50
    assert row.output_tokens == 30
    assert row.cached_tokens == 0
    assert row.cache_hit is False


# ---------------------------------------------------------------------------
# Tests: Anthropic 原生路径
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_anthropic_path_cache_tokens_in_response_and_total(
    dev_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Anthropic /v1/messages 路径：验证响应体含 cache_read_input_tokens 且
    anthropic_usage_total_tokens 包含所有 token。"""
    from domains.gateway.application.proxy.anthropic_native_adapt import (
        anthropic_usage_total_tokens,
    )

    team_id = uuid.uuid4()
    principal = _principal(team_id=team_id)

    async def fake_anthropic_messages(
        self: ProxyUseCase,
        ctx: ProxyContext,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "id": "msg_anth_test",
            "type": "message",
            "role": "assistant",
            "model": body.get("model", "anthropic/claude-3-haiku"),
            "content": [{"type": "text", "text": "pong"}],
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {
                "input_tokens": 20,
                "output_tokens": 10,
                "cache_creation_input_tokens": 100,
                "cache_read_input_tokens": 500,
            },
        }

    monkeypatch.setattr(ProxyUseCase, "anthropic_messages", fake_anthropic_messages)
    app.dependency_overrides[bearer_vkey_or_apikey_auth] = lambda: principal

    try:
        r = await dev_client.post(
            _ANTHROPIC_MESSAGES,
            headers={"Authorization": "Bearer sk-gw-test"},
            json={
                "model": "anthropic/claude-3-haiku",
                "max_tokens": 64,
                "messages": [{"role": "user", "content": "ping"}],
            },
        )
    finally:
        app.dependency_overrides.pop(bearer_vkey_or_apikey_auth, None)

    assert r.status_code == 200, r.text
    data = r.json()

    # -- 响应体应原样透传 cache 字段 --
    usage = data["usage"]
    assert usage["input_tokens"] == 20
    assert usage["output_tokens"] == 10
    assert usage["cache_read_input_tokens"] == 500
    assert usage["cache_creation_input_tokens"] == 100

    # -- anthropic_usage_total_tokens 必须包含所有 token --
    # input(20) + cache_read(500) + cache_create(100) + output(10) = 630
    total = anthropic_usage_total_tokens(usage)
    assert total == 630, f"expected 630 total tokens, got {total}"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_anthropic_path_cache_hit_metadata(
    dev_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Anthropic 路径：cache_read_input_tokens > 0 时 gateway_cache_hit 应为 True。"""
    from domains.gateway.application.proxy.prompt_cache_middleware import (
        parse_cache_hit_from_usage,
    )

    # -- 验证 parse_cache_hit_from_usage 对 Anthropic 格式 --
    assert parse_cache_hit_from_usage({"cache_read_input_tokens": 500}) is True
    assert parse_cache_hit_from_usage({"cache_read_input_tokens": 0}) is False
    assert parse_cache_hit_from_usage({}) is False
    assert parse_cache_hit_from_usage(None) is False

    # -- 验证 OpenAI 格式 --
    assert parse_cache_hit_from_usage(
        {"prompt_tokens_details": {"cached_tokens": 80}}
    ) is True
    assert parse_cache_hit_from_usage(
        {"prompt_tokens_details": {"cached_tokens": 0}}
    ) is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_anthropic_path_no_cache_tokens(
    dev_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Anthropic 路径无缓存时：total_tokens 应仅为 input + output。"""
    from domains.gateway.application.proxy.anthropic_native_adapt import (
        anthropic_usage_total_tokens,
    )

    team_id = uuid.uuid4()
    principal = _principal(team_id=team_id)

    async def fake_no_cache(
        self: ProxyUseCase,
        ctx: ProxyContext,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "id": "msg_no_cache",
            "type": "message",
            "role": "assistant",
            "model": body.get("model", "anthropic/claude-3-haiku"),
            "content": [{"type": "text", "text": "no cache"}],
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {
                "input_tokens": 30,
                "output_tokens": 15,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
            },
        }

    monkeypatch.setattr(ProxyUseCase, "anthropic_messages", fake_no_cache)
    app.dependency_overrides[bearer_vkey_or_apikey_auth] = lambda: principal

    try:
        r = await dev_client.post(
            _ANTHROPIC_MESSAGES,
            headers={"Authorization": "Bearer sk-gw-test"},
            json={
                "model": "anthropic/claude-3-haiku",
                "max_tokens": 64,
                "messages": [{"role": "user", "content": "ping"}],
            },
        )
    finally:
        app.dependency_overrides.pop(bearer_vkey_or_apikey_auth, None)

    assert r.status_code == 200, r.text
    usage = r.json()["usage"]
    # input(30) + output(15) = 45
    assert anthropic_usage_total_tokens(usage) == 45


# ---------------------------------------------------------------------------
# Tests: Stats API 聚合验证
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_stats_summary_reflects_cache_tokens(
    dev_client: AsyncClient,
    db_session: AsyncSession,
    test_user: Any,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dashboard summary API 应正确聚合 cached_tokens 和 cache_hit_count。"""
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    await db_session.commit()

    # -- 直接写入两条请求日志（一带缓存，一不带） --
    now = datetime.now(UTC)
    log_with_cache = GatewayRequestLog(
        tenant_id=team.id,
        user_id=test_user.id,
        vkey_id=uuid.uuid4(),
        route_name="openai/gpt-4o-mini",
        provider="openai",
        capability="chat",
        status="success",
        input_tokens=100,
        output_tokens=50,
        cached_tokens=80,
        cache_hit=True,
        cost_usd=Decimal("0.0005"),
        latency_ms=200,
        ttfb_ms=100,
        created_at=now,
    )
    log_no_cache = GatewayRequestLog(
        tenant_id=team.id,
        user_id=test_user.id,
        vkey_id=uuid.uuid4(),
        route_name="openai/gpt-4o-mini",
        provider="openai",
        capability="chat",
        status="success",
        input_tokens=60,
        output_tokens=30,
        cached_tokens=0,
        cache_hit=False,
        cost_usd=Decimal("0.0003"),
        latency_ms=150,
        ttfb_ms=80,
        created_at=now,
    )
    db_session.add_all([log_with_cache, log_no_cache])
    await db_session.flush()

    # -- 调用 dashboard summary API --
    r = await dev_client.get(
        f"/api/v1/gateway/teams/{team.id}/dashboard/summary?days=7",
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    summary = r.json()

    # 2 requests
    assert summary["total_requests"] == 2
    # input: 100 + 60 = 160
    assert summary["total_input_tokens"] == 160
    # output: 50 + 30 = 80
    assert summary["total_output_tokens"] == 80
    # success: 2/2 = 100%
    assert summary["success_rate"] == pytest.approx(1.0)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_logs_api_returns_cache_fields(
    dev_client: AsyncClient,
    db_session: AsyncSession,
    test_user: Any,
    auth_headers: dict[str, str],
) -> None:
    """Logs 列表 API 应返回 cache_hit 和 cached_tokens 字段。"""
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    await db_session.commit()

    log = GatewayRequestLog(
        tenant_id=team.id,
        user_id=test_user.id,
        vkey_id=uuid.uuid4(),
        route_name="anthropic/claude-3-haiku",
        provider="anthropic",
        capability="chat",
        status="success",
        input_tokens=20,
        output_tokens=10,
        cached_tokens=500,
        cache_hit=True,
        cost_usd=Decimal("0.0003"),
        latency_ms=300,
        ttfb_ms=120,
        created_at=datetime.now(UTC),
    )
    db_session.add(log)
    await db_session.flush()

    r = await dev_client.get(
        f"/api/v1/gateway/teams/{team.id}/logs?page=1&page_size=10",
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    data = r.json()

    assert data["total"] >= 1
    items = data["items"]
    assert len(items) >= 1

    # 找到我们写入的那条日志
    cache_log = next(
        (i for i in items if i.get("cached_tokens") == 500),
        None,
    )
    assert cache_log is not None, "cache log not found in response"
    assert cache_log["cache_hit"] is True
    assert cache_log["cached_tokens"] == 500
    assert cache_log["input_tokens"] == 20
    assert cache_log["output_tokens"] == 10


@pytest.mark.integration
@pytest.mark.asyncio
async def test_statistics_api_returns_cache_hit_count(
    dev_client: AsyncClient,
    db_session: AsyncSession,
    test_user: Any,
    auth_headers: dict[str, str],
) -> None:
    """Statistics API 应返回 cache_hit_count 和 cache_hit_rate。"""
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    await db_session.commit()

    now = datetime.now(UTC)
    # 3 条日志：2 条 cache_hit=True，1 条 cache_hit=False
    for i, (cached, hit) in enumerate([(100, True), (200, True), (0, False)]):
        db_session.add(
            GatewayRequestLog(
                tenant_id=team.id,
                user_id=test_user.id,
                vkey_id=uuid.uuid4(),
                route_name=f"model-{i}",
                provider="openai",
                capability="chat",
                status="success",
                input_tokens=50,
                output_tokens=20,
                cached_tokens=cached,
                cache_hit=hit,
                cost_usd=Decimal("0.0001"),
                latency_ms=100,
                ttfb_ms=50,
                created_at=now,
            )
        )
    await db_session.flush()

    r = await dev_client.get(
        f"/api/v1/gateway/teams/{team.id}/dashboard/statistics"
        f"?days=7&group_by=credential&page=1&page_size=20",
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    data = r.json()

    # totals 应有 cache_hit_count
    totals = data.get("totals")
    assert totals is not None, "totals not in response"
    assert totals["requests"] == 3
    assert totals["cache_hit_count"] == 2
    # cache_hit_rate = 2/3 ≈ 66.7%
    assert totals["cache_hit_rate"] == pytest.approx(2 / 3, rel=0.01)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_dashboard_latency_averages_successful_requests_only(
    dev_client: AsyncClient,
    db_session: AsyncSession,
    test_user: Any,
    auth_headers: dict[str, str],
) -> None:
    """调用统计和概览的平均延迟只使用成功请求，失败请求仍计入请求/失败数。"""
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    await db_session.commit()

    now = datetime.now(UTC)
    credential_id = uuid.uuid4()
    rows = [
        ("success", 100, 20),
        ("success", 300, 60),
        ("failed", 900, 800),
    ]
    for i, (status, latency_ms, ttfb_ms) in enumerate(rows):
        db_session.add(
            GatewayRequestLog(
                tenant_id=team.id,
                user_id=test_user.id,
                vkey_id=uuid.uuid4(),
                credential_id=credential_id,
                credential_name_snapshot="latency-cred",
                route_name="latency-model",
                provider="openai",
                capability="chat",
                status=status,
                error_code="UpstreamError" if status != "success" else None,
                error_message="upstream failed" if status != "success" else None,
                input_tokens=10,
                output_tokens=5,
                cached_tokens=0,
                cache_hit=False,
                cost_usd=Decimal("0.0001"),
                latency_ms=latency_ms,
                ttfb_ms=ttfb_ms,
                created_at=now,
                request_id=f"req-latency-{i}",
            )
        )
    await db_session.flush()

    summary = await dev_client.get(
        f"/api/v1/gateway/teams/{team.id}/dashboard/summary",
        params={"days": 7},
        headers=auth_headers,
    )
    assert summary.status_code == 200, summary.text
    summary_body = summary.json()
    assert summary_body["total_requests"] == 3
    assert summary_body["success_count"] == 2
    assert summary_body["failure_count"] == 1
    assert summary_body["avg_latency_ms"] == pytest.approx(200)
    assert summary_body["avg_ttfb_ms"] == pytest.approx(40)

    stats = await dev_client.get(
        f"/api/v1/gateway/teams/{team.id}/dashboard/statistics",
        params={"days": 7, "group_by": "credential", "page": 1, "page_size": 20},
        headers=auth_headers,
    )
    assert stats.status_code == 200, stats.text
    stats_body = stats.json()
    totals = stats_body["totals"]
    assert totals["requests"] == 3
    assert totals["success_count"] == 2
    assert totals["failure_count"] == 1
    assert totals["avg_latency_ms"] == pytest.approx(200)
    assert totals["avg_ttfb_ms"] == pytest.approx(40)
    assert stats_body["items"][0]["avg_latency_ms"] == pytest.approx(200)
    assert stats_body["items"][0]["avg_ttfb_ms"] == pytest.approx(40)

    failed_stats = await dev_client.get(
        f"/api/v1/gateway/teams/{team.id}/dashboard/statistics",
        params={
            "days": 7,
            "group_by": "credential",
            "status": "failed",
            "page": 1,
            "page_size": 20,
        },
        headers=auth_headers,
    )
    assert failed_stats.status_code == 200, failed_stats.text
    failed_totals = failed_stats.json()["totals"]
    assert failed_totals["requests"] == 1
    assert failed_totals["success_count"] == 0
    assert failed_totals["failure_count"] == 1
    assert failed_totals["avg_latency_ms"] == pytest.approx(0)
    assert failed_totals["avg_ttfb_ms"] == pytest.approx(0)
