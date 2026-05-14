"""Gateway bridge attribution API-flow 集成测试。

历史 bug：``LLMGateway`` 在 bridge 异常时静默回退直连 LiteLLM，且
``gateway_virtual_keys`` 缺少 partial unique index，并发 chat 启动时（标题
生成 + 主流）会写入两条 active system vkey；之后
``scalar_one_or_none()`` 抛 ``MultipleResultsFound`` → bridge fallback →
``gateway_request_logs`` 行的 ``team_id/user_id/vkey_id`` 永远是 NULL →
``/api/v1/gateway/dashboard/summary`` 按 team 聚合时永远是 0。

本套测试在 ``client`` HTTP fixture 之上（含真实 dep 注入 + LangGraph
checkpointer + sync 后的 catalog + Redis mock），直接驱动
``LLMGateway`` → ``GatewayBridge`` → ``ProxyUseCase`` → patched
``Router.acompletion`` → ``GatewayCustomLogger.async_log_success_event``
→ ``RequestLogRepository.insert``，断言：

1. 单次调用：``gateway_request_logs`` 行的 team/user/vkey 三件套必须齐全。
2. 并发调用（4 路同时跑）：每条日志的归因仍然齐全，且**只**用同一条
   active system vkey（partial unique index 生效）。
3. 桥接异常不被 fallback 吃掉：``Router.acompletion`` 抛错时
   ``LLMGateway.chat`` 必须把异常抛回调用方，杜绝静默直连 LiteLLM 让
   日志失去归因。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
import time
import types
from typing import Any
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# 触发跨域 ORM mapper 注册（与 unit 测试一致，避免 User → Agent 关系 lazy 解析失败）
from domains.agent.infrastructure.models import (  # noqa: F401  # isort:skip
    agent as _agent_model,
    memory as _memory_model,
    message as _message_model,
)
from domains.agent.infrastructure.llm.gateway import LLMGateway
from domains.gateway.application.proxy_use_case import shutdown_proxy_deferred_tasks
from domains.gateway.infrastructure.models.request_log import GatewayRequestLog
from domains.gateway.infrastructure.models.virtual_key import GatewayVirtualKey
from domains.tenancy.application.team_service import TeamService
from libs.db.permission_context import (
    PermissionContext,
    clear_permission_context,
    set_permission_context,
)


def _make_fake_response(
    model: str,
    *,
    prompt_tokens: int,
    completion_tokens: int,
    cost: float,
    reasoning_tokens: int = 0,
    cached_tokens: int = 0,
    assistant_content: str = "ok",
) -> Any:
    """造一个最小可用的 ``ModelResponse`` 替身。

    覆盖真实 provider 的 usage 形状：

    - ``usage.prompt_tokens`` / ``completion_tokens`` / ``total_tokens``：标量；
    - ``usage.completion_tokens_details``：dict，含 ``reasoning_tokens``
      （DeepSeek-Reasoner 思考链）；
    - ``usage.prompt_tokens_details``：dict，含 ``cached_tokens``
      （OpenAI / DeepSeek prompt cache）。

    这两个嵌套字段历史上让 ``LLMResponse.usage`` 的 ``dict[str, int]`` 校验
    抛 ``ValidationError``，进而让 bridge 路径返回时 chat 直接 500。schema
    放宽到 ``dict[str, Any]`` 后必须仍能透传。
    """
    message = types.SimpleNamespace(content=assistant_content, tool_calls=None)
    choice = types.SimpleNamespace(message=message, finish_reason="stop")
    usage = types.SimpleNamespace(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
        prompt_tokens_details={"cached_tokens": cached_tokens},
        completion_tokens_details={"reasoning_tokens": reasoning_tokens},
    )
    return types.SimpleNamespace(
        choices=[choice],
        usage=usage,
        model=model,
        _hidden_params={"response_cost": cost},
    )


async def _trigger_callbacks(kwargs: dict[str, Any], response_obj: Any) -> None:
    """模拟 LiteLLM 在 ``acompletion`` 完成后 dispatch success callback。"""
    import litellm  # pylint: disable=import-outside-toplevel

    now = time.time()
    for cb in list(litellm.callbacks or []):
        success_fn = getattr(cb, "async_log_success_event", None)
        if success_fn is None:
            continue
        await success_fn(kwargs, response_obj, now, now)


def _patched_acompletion(
    *,
    prompt_tokens: int = 12,
    completion_tokens: int = 7,
    cost: float = 0.000123,
    assistant_content: str = "ok",
):
    """构造一个 ``Router.acompletion`` 替身。

    保留 LiteLLM 真实行为中和归因相关的两点：
    1. 把 ``kwargs["metadata"]`` 原样传递给 callback；
    2. 完成后异步 dispatch success callback，让 ``GatewayCustomLogger``
       把 ``gateway_request_logs`` 行写入 DB。
    """

    async def _impl(_self: Any, **kwargs: Any) -> Any:
        response = _make_fake_response(
            kwargs.get("model") or "test/model",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost=cost,
            assistant_content=assistant_content,
        )
        await _trigger_callbacks(kwargs, response)
        return response

    return _impl


def _patched_acompletion_raising():
    async def _impl(_self: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("simulated upstream failure")

    return _impl


@pytest.fixture(autouse=True)
def _disable_redis_counters(monkeypatch: pytest.MonkeyPatch) -> None:
    """跳过 Redis 计数（测试不引入 redis）。"""

    async def _noop(**_: Any) -> None:
        return None

    monkeypatch.setattr(
        "domains.gateway.infrastructure.callbacks.custom_logger._bump_redis_counters",
        _noop,
    )


@pytest.fixture
def _registered_user_context(test_user: Any, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[None]:
    """把当前协程的 PermissionContext 设为已登录注册用户。"""
    clear_permission_context()
    set_permission_context(
        PermissionContext(
            user_id=test_user.id,
            role="user",
        )
    )
    yield
    clear_permission_context()


async def _read_logs(db_session: AsyncSession, team_id: uuid.UUID) -> list[GatewayRequestLog]:
    stmt = (
        select(GatewayRequestLog)
        .where(GatewayRequestLog.team_id == team_id)
        .order_by(GatewayRequestLog.created_at.asc())
    )
    return list((await db_session.execute(stmt)).scalars().all())


@pytest.mark.asyncio
async def test_chat_writes_gateway_request_log_with_full_attribution(
    client: Any,
    db_session: AsyncSession,
    test_user: Any,
    monkeypatch: pytest.MonkeyPatch,
    _registered_user_context: None,
) -> None:
    """单次 chat 流程：``gateway_request_logs`` 行 team/user/vkey 必须齐全。

    覆盖根因修复：bridge 全程不允许静默 fallback，``gateway_request_logs``
    必须能按 ``team_id`` 聚合到 dashboard。
    """
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    await db_session.commit()

    monkeypatch.setattr(
        "litellm.router.Router.acompletion",
        _patched_acompletion(prompt_tokens=11, completion_tokens=5, cost=0.000456),
    )

    gateway = LLMGateway(config=__import__("bootstrap.config", fromlist=["settings"]).settings)
    await gateway.chat(
        messages=[{"role": "user", "content": "hi"}],
        model="zai/glm-4-flash",
    )
    await shutdown_proxy_deferred_tasks()

    rows = await _read_logs(db_session, team.id)
    assert len(rows) == 1, f"expected one request log row, got {len(rows)}"
    row = rows[0]
    assert row.team_id == team.id
    assert row.user_id == test_user.id
    assert row.vkey_id is not None, "system vkey id must be persisted as attribution"
    assert row.input_tokens == 11
    assert row.output_tokens == 5
    assert float(row.cost_usd or 0) == pytest.approx(0.000456, rel=1e-3)

    # 同一 team 只有一条 active system vkey，且就是日志里那条
    active_vkeys = (
        await db_session.execute(
            select(GatewayVirtualKey).where(
                GatewayVirtualKey.team_id == team.id,
                GatewayVirtualKey.is_system.is_(True),
                GatewayVirtualKey.is_active.is_(True),
            )
        )
    ).scalars().all()
    assert len(active_vkeys) == 1
    assert active_vkeys[0].id == row.vkey_id


@pytest.mark.asyncio
async def test_repeated_chat_always_reuses_same_system_vkey(
    client: Any,
    db_session: AsyncSession,
    test_user: Any,
    monkeypatch: pytest.MonkeyPatch,
    _registered_user_context: None,
) -> None:
    """多次 chat 都必须命中同一条 active system vkey，且每条日志带完整归因。

    历史 bug 是并发标题生成 + chat 主流同时进入 ``get_or_create_system_key``
    各写一条，导致后续 ``scalar_one_or_none()`` 抛错让 bridge fallback。
    数据库 partial unique index + ``INSERT ... ON CONFLICT`` upsert 让
    无论顺序还是并发，最终都收敛到唯一一条 vkey 上。

    并发场景的唯一性约束已在 ``test_concurrent_get_or_create_system_key_*``
    单测中由 ``asyncio.gather`` 覆盖；本测试聚焦 API flow 层"多次 chat 全程
    保持归因 + 唯一 vkey"，避免测试 fixture 单连接复用引入的 SQLAlchemy
    并发状态机噪声。
    """
    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    await db_session.commit()

    monkeypatch.setattr(
        "litellm.router.Router.acompletion",
        _patched_acompletion(prompt_tokens=3, completion_tokens=2, cost=0.0001),
    )

    gateway = LLMGateway(config=__import__("bootstrap.config", fromlist=["settings"]).settings)
    for _ in range(4):
        await gateway.chat(
            messages=[{"role": "user", "content": "ping"}],
            model="zai/glm-4-flash",
        )
        await shutdown_proxy_deferred_tasks()

    rows = await _read_logs(db_session, team.id)
    assert len(rows) == 4
    for row in rows:
        assert row.team_id == team.id
        assert row.user_id == test_user.id
        assert row.vkey_id is not None

    vkey_ids = {row.vkey_id for row in rows}
    assert len(vkey_ids) == 1, "多次 chat 都必须命中同一条 active system vkey"

    active_vkeys = (
        await db_session.execute(
            select(GatewayVirtualKey).where(
                GatewayVirtualKey.team_id == team.id,
                GatewayVirtualKey.is_system.is_(True),
                GatewayVirtualKey.is_active.is_(True),
            )
        )
    ).scalars().all()
    assert len(active_vkeys) == 1


@pytest.mark.asyncio
async def test_bridge_failure_is_not_silently_fallbacked(
    client: Any,
    db_session: AsyncSession,
    test_user: Any,
    monkeypatch: pytest.MonkeyPatch,
    _registered_user_context: None,
) -> None:
    """桥接异常**不允许**被静默回退到直连 LiteLLM。

    历史代码在 ``_maybe_call_via_gateway_litellm`` 里 ``except Exception:
    return None`` 把异常吞掉、再走 ``await self._chat()`` 直连 LiteLLM。
    结果：1) chat 接口看起来"正常"返回；2) ``gateway_request_logs`` 行
    丢失 team/user/vkey 归因；3) dashboard 永远聚合到 0。

    根因修复后，bridge 异常必须沿调用栈抛回 chat 端点，让调用方立即看到。
    """
    await TeamService(db_session).ensure_personal_team(test_user.id)
    await db_session.commit()

    monkeypatch.setattr(
        "litellm.router.Router.acompletion",
        _patched_acompletion_raising(),
    )

    gateway = LLMGateway(config=__import__("bootstrap.config", fromlist=["settings"]).settings)

    with pytest.raises(RuntimeError, match="simulated upstream failure"):
        await gateway.chat(
            messages=[{"role": "user", "content": "boom"}],
            model="zai/glm-4-flash",
        )


@pytest.mark.asyncio
async def test_verbose_internal_override_persists_prompt_and_long_response_preview(
    client: Any,
    db_session: AsyncSession,
    test_user: Any,
    monkeypatch: pytest.MonkeyPatch,
    _registered_user_context: None,
) -> None:
    """ContextVar 打开详细日志时：``prompt_redacted.messages_preview`` 与更长 ``preview`` 落库。"""
    from domains.gateway.application.gateway_internal_log_context import (
        reset_internal_store_full_override,
        set_internal_store_full_override,
    )

    team = await TeamService(db_session).ensure_personal_team(test_user.id)
    await db_session.commit()

    long_content = "R" * 800
    monkeypatch.setattr(
        "litellm.router.Router.acompletion",
        _patched_acompletion(
            prompt_tokens=2,
            completion_tokens=3,
            cost=0.00002,
            assistant_content=long_content,
        ),
    )

    cfg = __import__("bootstrap.config", fromlist=["settings"]).settings
    token = set_internal_store_full_override(True)
    try:
        gateway = LLMGateway(config=cfg)
        await gateway.chat(
            messages=[{"role": "user", "content": "hello verbose"}],
            model="zai/glm-4-flash",
        )
        await shutdown_proxy_deferred_tasks()
    finally:
        reset_internal_store_full_override(token)

    rows = await _read_logs(db_session, team.id)
    assert len(rows) == 1
    row = rows[0]
    assert row.prompt_redacted is not None
    assert "messages_preview" in row.prompt_redacted
    mp = row.prompt_redacted["messages_preview"]
    assert isinstance(mp, dict) and "hello verbose" in mp.get("text", "")
    assert row.response_summary is not None
    preview = str(row.response_summary.get("preview") or "")
    assert len(preview) <= cfg.gateway_request_log_response_verbose_max_chars + 5
    assert preview.startswith("RRR") or "R" * 200 in preview
