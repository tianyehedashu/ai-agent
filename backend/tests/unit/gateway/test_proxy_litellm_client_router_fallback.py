"""_invoke_router_or_direct 在 Router 缺少方法时的 deployment 凭据注入。

以及 _merge_deployment_params_into_kwargs 的单元测试。"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from domains.gateway.application.proxy_litellm_client import ProxyLiteLLMClient


def _make_router_without_method() -> MagicMock:
    """构造一个没有 aanthropic_messages 的 Router mock。"""
    router = MagicMock(spec=[])
    return router


# 顶部导入的函数 patch 路径统一用 proxy_litellm_client 模块
_MOD = "domains.gateway.application.proxy_litellm_client"


@pytest.mark.asyncio
async def test_fallback_merges_deployment_params_when_router_lacks_method(
    db_session: AsyncSession,
) -> None:
    """Router 没有 aanthropic_messages 时，fallback 到 direct 前应注入 deployment 凭据。"""
    team_id = uuid.uuid4()
    client_model = "glm-5-1"
    encoded_model = f"gw/t/{team_id}/{client_model}"

    kwargs: dict[str, Any] = {
        "model": encoded_model,
        "messages": [{"role": "user", "content": "hello"}],
        "max_tokens": 1024,
        "metadata": {"user_api_key_team_id": str(team_id)},
    }

    # Router 没有 aanthropic_messages
    router = _make_router_without_method()

    # deployment 参数（模拟 resolve_deployment_litellm_params 返回值）
    dep_params: dict[str, Any] = {
        "model": "glm-5.1",
        "custom_llm_provider": "openai",
        "api_key": "sk-test-key",
        "api_base": "https://zhenze-huhehaote.cmecloud.cn/api/coding/v1",
    }

    client = ProxyLiteLLMClient(db_session)

    with (
        patch(f"{_MOD}.ensure_router_deployment", new_callable=AsyncMock, return_value=router),
        patch(
            f"{_MOD}.resolve_deployment_litellm_params",
            new_callable=AsyncMock,
            return_value=dep_params,
        ),
        patch(f"{_MOD}.filter_litellm_params_for_direct_anthropic", side_effect=lambda d: dict(d)),
        patch(f"{_MOD}.ensure_litellm_router_team_metadata"),
        patch("domains.gateway.infrastructure.router_singleton.ensure_gateway_callbacks"),
        patch(
            "litellm.anthropic_messages",
            new_callable=AsyncMock,
            return_value={"role": "assistant", "content": "hi"},
        ) as mock_litellm_anthropic,
    ):
        await client._invoke_router_or_direct(
            router_method="aanthropic_messages",
            direct_call=lambda: client.direct_anthropic_messages(kwargs),
            kwargs=kwargs,
        )

        # 验证 kwargs 中的 model 已从 Router 编码名替换为 deployment 的 litellm model
        assert kwargs["model"] == "glm-5.1", (
            f"model 应被替换为 deployment 的 litellm model，实际: {kwargs['model']}"
        )
        # 验证凭据已注入
        assert kwargs.get("custom_llm_provider") == "openai"
        assert kwargs.get("api_key") == "sk-test-key"
        assert kwargs.get("api_base") == "https://zhenze-huhehaote.cmecloud.cn/api/coding/v1"

        # 验证 litellm.anthropic_messages 被调用且参数正确
        mock_litellm_anthropic.assert_called_once()
        call_kwargs = mock_litellm_anthropic.call_args[1]
        assert call_kwargs["model"] == "glm-5.1"
        assert call_kwargs["custom_llm_provider"] == "openai"


@pytest.mark.asyncio
async def test_no_fallback_merge_when_router_has_method(
    db_session: AsyncSession,
) -> None:
    """Router 有 acompletion 方法时，不应走 fallback merge 逻辑。"""
    team_id = uuid.uuid4()
    client_model = "gpt-4o"
    encoded_model = f"gw/t/{team_id}/{client_model}"

    kwargs: dict[str, Any] = {
        "model": encoded_model,
        "messages": [{"role": "user", "content": "hello"}],
    }

    # Router 有 acompletion
    router_fn = AsyncMock(return_value={"choices": []})
    router = MagicMock(acompletion=router_fn)

    client = ProxyLiteLLMClient(db_session)

    with (
        patch(f"{_MOD}.ensure_router_deployment", new_callable=AsyncMock, return_value=router),
        patch(f"{_MOD}.resolve_deployment_litellm_params", new_callable=AsyncMock) as mock_resolve,
        patch(f"{_MOD}.ensure_litellm_router_team_metadata"),
        patch("domains.gateway.infrastructure.router_singleton.ensure_gateway_callbacks"),
    ):
        await client._invoke_router_or_direct(
            router_method="acompletion",
            direct_call=AsyncMock,
            kwargs=kwargs,
        )

        # Router 有 acompletion，不应调用 resolve_deployment_litellm_params
        mock_resolve.assert_not_called()
        # model 不应被修改
        assert kwargs["model"] == encoded_model


@pytest.mark.asyncio
async def test_fallback_no_merge_when_decode_fails(
    db_session: AsyncSession,
) -> None:
    """encoded model 名无法解码时（非 gw/t/ 或 gw/s/ 前缀），不应 merge。"""
    kwargs: dict[str, Any] = {
        "model": "plain-model-name",
        "messages": [{"role": "user", "content": "hello"}],
    }

    router = _make_router_without_method()
    direct_called = False

    async def _direct() -> dict[str, Any]:
        nonlocal direct_called
        direct_called = True
        return {"ok": True}

    client = ProxyLiteLLMClient(db_session)

    with (
        patch(f"{_MOD}.ensure_router_deployment", new_callable=AsyncMock, return_value=router),
        patch(f"{_MOD}.resolve_deployment_litellm_params", new_callable=AsyncMock) as mock_resolve,
        patch(f"{_MOD}.ensure_litellm_router_team_metadata"),
        patch("domains.gateway.infrastructure.router_singleton.ensure_gateway_callbacks"),
    ):
        await client._invoke_router_or_direct(
            router_method="aanthropic_messages",
            direct_call=_direct,
            kwargs=kwargs,
        )

        # model 名无法解码，不应调用 resolve_deployment_litellm_params
        mock_resolve.assert_not_called()
        assert direct_called
        # model 不应被修改
        assert kwargs["model"] == "plain-model-name"


@pytest.mark.asyncio
async def test_fallback_no_merge_when_deployment_not_found(
    db_session: AsyncSession,
) -> None:
    """deployment 解析返回 None 时，kwargs 不应被修改但仍走 direct。"""
    team_id = uuid.uuid4()
    encoded_model = f"gw/t/{team_id}/unknown-model"

    kwargs: dict[str, Any] = {
        "model": encoded_model,
        "messages": [{"role": "user", "content": "hello"}],
    }

    router = _make_router_without_method()
    direct_called = False

    async def _direct() -> dict[str, Any]:
        nonlocal direct_called
        direct_called = True
        return {"ok": True}

    client = ProxyLiteLLMClient(db_session)

    with (
        patch(f"{_MOD}.ensure_router_deployment", new_callable=AsyncMock, return_value=router),
        patch(
            f"{_MOD}.resolve_deployment_litellm_params", new_callable=AsyncMock, return_value=None
        ),
        patch(f"{_MOD}.ensure_litellm_router_team_metadata"),
        patch("domains.gateway.infrastructure.router_singleton.ensure_gateway_callbacks"),
    ):
        await client._invoke_router_or_direct(
            router_method="aanthropic_messages",
            direct_call=_direct,
            kwargs=kwargs,
        )

        assert direct_called
        # model 不应被修改
        assert kwargs["model"] == encoded_model


# ---------- _merge_deployment_params_into_kwargs 单元测试 ----------


def test_merge_deployment_params_replaces_model() -> None:
    """deployment 的 model 字段应替换 kwargs 中的 model。"""
    kwargs: dict[str, Any] = {
        "model": "gw/t/some-team/glm-5-1",
        "messages": [{"role": "user", "content": "hi"}],
    }
    dep: dict[str, Any] = {
        "model": "glm-5.1",
        "custom_llm_provider": "zhipuai",
        "api_key": "sk-xxx",
        "api_base": "https://open.bigmodel.cn/api/paas/v4",
    }
    ProxyLiteLLMClient._merge_deployment_params_into_kwargs(kwargs, dep)
    assert kwargs["model"] == "glm-5.1"
    assert kwargs["custom_llm_provider"] == "zhipuai"
    assert kwargs["api_key"] == "sk-xxx"
    assert kwargs["api_base"] == "https://open.bigmodel.cn/api/paas/v4"


def test_merge_deployment_params_does_not_overwrite_existing() -> None:
    """kwargs 中已有非空值时，deployment 参数不应覆盖。"""
    kwargs: dict[str, Any] = {
        "model": "gw/t/team/glm-5-1",
        "api_key": "existing-key",
        "messages": [],
    }
    dep: dict[str, Any] = {
        "model": "glm-5.1",
        "api_key": "dep-key",
        "custom_llm_provider": "zhipuai",
    }
    ProxyLiteLLMClient._merge_deployment_params_into_kwargs(kwargs, dep)
    assert kwargs["model"] == "glm-5.1"  # model 总是替换
    assert kwargs["api_key"] == "existing-key"  # 已有值不覆盖
    assert kwargs["custom_llm_provider"] == "zhipuai"  # 新字段注入


def test_merge_deployment_params_overwrites_empty() -> None:
    """kwargs 中值为空字符串时，deployment 参数应覆盖。"""
    kwargs: dict[str, Any] = {
        "model": "gw/t/team/model",
        "api_key": "",
        "api_base": None,
        "messages": [],
    }
    dep: dict[str, Any] = {
        "model": "real-model",
        "api_key": "sk-dep",
        "api_base": "https://api.example.com/v1",
    }
    ProxyLiteLLMClient._merge_deployment_params_into_kwargs(kwargs, dep)
    assert kwargs["api_key"] == "sk-dep"
    assert kwargs["api_base"] == "https://api.example.com/v1"


def test_merge_deployment_params_strips_router_only_fields() -> None:
    """rpm / tpm / pricing 等 Router 调度字段不应注入 kwargs。"""
    kwargs: dict[str, Any] = {"model": "gw/t/team/model", "messages": []}
    dep: dict[str, Any] = {
        "model": "real-model",
        "custom_llm_provider": "openai",
        "api_key": "sk-xxx",
        "rpm": 100,
        "tpm": 10000,
        "input_cost_per_token": 0.00001,
    }
    ProxyLiteLLMClient._merge_deployment_params_into_kwargs(kwargs, dep)
    assert "rpm" not in kwargs
    assert "tpm" not in kwargs
    assert "input_cost_per_token" not in kwargs
    assert kwargs["custom_llm_provider"] == "openai"
