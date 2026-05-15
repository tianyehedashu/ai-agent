"""ProxyUseCase._build_metadata 安全与注入字段单测。"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
import uuid

import pytest

from domains.gateway.application.proxy_use_case import ProxyContext, ProxyUseCase
from domains.gateway.domain.errors import CapabilityNotAllowedError, ModelNotAllowedError
from domains.gateway.domain.types import GatewayCapability, VirtualKeyPrincipal


@pytest.mark.asyncio
async def test_build_metadata_ignores_user_gateway_prefix_keys(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Any,
) -> None:
    monkeypatch.setattr(
        "domains.gateway.application.proxy_use_case.TeamRepository.get",
        AsyncMock(return_value=MagicMock(name="t", kind="personal")),
    )

    tid = uuid.uuid4()
    uid = uuid.uuid4()
    vid = uuid.uuid4()
    vkey = VirtualKeyPrincipal(
        vkey_id=vid,
        vkey_name="k",
        team_id=tid,
        user_id=uid,
        allowed_models=(),
        allowed_capabilities=(GatewayCapability.CHAT,),
        rpm_limit=None,
        tpm_limit=None,
        store_full_messages=False,
        guardrail_enabled=True,
        is_system=True,
    )
    ctx = ProxyContext(
        team_id=tid,
        user_id=uid,
        vkey=vkey,
        capability=GatewayCapability.CHAT,
        request_id="rid",
        store_full_messages=False,
        guardrail_enabled=True,
    )
    uc = ProxyUseCase(db_session)
    meta = await uc._build_metadata(
        ctx,
        user_kwargs={
            "metadata": {
                "gateway_evil": "injected",
                "safe_client_marker": 42,
            }
        },
    )
    assert "gateway_evil" not in meta
    assert meta.get("safe_client_marker") == 42
    assert meta["gateway_team_id"] == str(tid)
    assert meta["gateway_store_full_messages"] is False
    assert meta["gateway_inbound_via"] == "vkey"
    assert meta["gateway_platform_api_key_id"] is None


@pytest.mark.asyncio
async def test_build_metadata_verbose_sets_response_max_chars(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Any,
) -> None:
    from bootstrap.config import settings

    monkeypatch.setattr(
        "domains.gateway.application.proxy_use_case.TeamRepository.get",
        AsyncMock(return_value=MagicMock(name="t", kind="personal")),
    )

    tid = uuid.uuid4()
    uid = uuid.uuid4()
    vid = uuid.uuid4()
    vkey = VirtualKeyPrincipal(
        vkey_id=vid,
        vkey_name="k",
        team_id=tid,
        user_id=uid,
        allowed_models=(),
        allowed_capabilities=(GatewayCapability.CHAT,),
        rpm_limit=None,
        tpm_limit=None,
        store_full_messages=True,
        guardrail_enabled=True,
        is_system=True,
    )
    ctx = ProxyContext(
        team_id=tid,
        user_id=uid,
        vkey=vkey,
        capability=GatewayCapability.CHAT,
        request_id="rid",
        store_full_messages=True,
        guardrail_enabled=True,
    )
    uc = ProxyUseCase(db_session)
    meta = await uc._build_metadata(ctx, user_kwargs=None)
    assert meta["gateway_store_full_messages"] is True
    assert meta["gateway_inbound_via"] == "vkey"
    assert meta["gateway_platform_api_key_id"] is None
    assert meta["gateway_log_response_max_chars"] == int(
        settings.gateway_request_log_response_verbose_max_chars
    )


@pytest.mark.asyncio
async def test_build_metadata_apikey_inbound_sets_platform_key_id(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Any,
) -> None:
    monkeypatch.setattr(
        "domains.gateway.application.proxy_use_case.TeamRepository.get",
        AsyncMock(return_value=MagicMock(name="t", kind="personal")),
    )

    tid = uuid.uuid4()
    uid = uuid.uuid4()
    akid = uuid.uuid4()
    ctx = ProxyContext(
        team_id=tid,
        user_id=uid,
        vkey=None,
        capability=GatewayCapability.CHAT,
        request_id="rid",
        store_full_messages=False,
        guardrail_enabled=True,
        inbound_via="apikey",
        platform_api_key_id=akid,
    )
    uc = ProxyUseCase(db_session)
    meta = await uc._build_metadata(ctx, user_kwargs=None)
    assert meta["gateway_inbound_via"] == "apikey"
    assert meta["gateway_platform_api_key_id"] == str(akid)
    assert meta["gateway_vkey_id"] is None


@pytest.mark.asyncio
async def test_build_metadata_injects_gateway_route_snapshot_when_cache_hit(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Any,
) -> None:
    monkeypatch.setattr(
        "domains.gateway.application.proxy_use_case.TeamRepository.get",
        AsyncMock(return_value=MagicMock(name="t", kind="personal")),
    )
    snap = {
        "virtual_model": "vm1",
        "primary_models": ["p1"],
        "strategy": "fallback",
    }
    monkeypatch.setattr(
        "domains.gateway.application.proxy_use_case.get_route_snapshot_metadata",
        AsyncMock(return_value=snap),
    )
    monkeypatch.setattr(
        ProxyUseCase,
        "_credential_metadata_for_virtual_model",
        AsyncMock(return_value={}),
    )

    tid = uuid.uuid4()
    uid = uuid.uuid4()
    vid = uuid.uuid4()
    vkey = VirtualKeyPrincipal(
        vkey_id=vid,
        vkey_name="k",
        team_id=tid,
        user_id=uid,
        allowed_models=(),
        allowed_capabilities=(GatewayCapability.CHAT,),
        rpm_limit=None,
        tpm_limit=None,
        store_full_messages=False,
        guardrail_enabled=True,
        is_system=True,
    )
    ctx = ProxyContext(
        team_id=tid,
        user_id=uid,
        vkey=vkey,
        capability=GatewayCapability.CHAT,
        request_id="rid",
        store_full_messages=False,
        guardrail_enabled=True,
    )
    uc = ProxyUseCase(db_session)
    meta = await uc._build_metadata(ctx, user_kwargs={"model": "vm1"})
    assert meta["gateway_route_snapshot"] == snap


@pytest.mark.asyncio
async def test_build_metadata_omits_gateway_route_snapshot_when_cache_miss(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Any,
) -> None:
    monkeypatch.setattr(
        "domains.gateway.application.proxy_use_case.TeamRepository.get",
        AsyncMock(return_value=MagicMock(name="t", kind="personal")),
    )
    monkeypatch.setattr(
        "domains.gateway.application.proxy_use_case.get_route_snapshot_metadata",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        ProxyUseCase,
        "_credential_metadata_for_virtual_model",
        AsyncMock(return_value={}),
    )

    tid = uuid.uuid4()
    uid = uuid.uuid4()
    vid = uuid.uuid4()
    vkey = VirtualKeyPrincipal(
        vkey_id=vid,
        vkey_name="k",
        team_id=tid,
        user_id=uid,
        allowed_models=(),
        allowed_capabilities=(GatewayCapability.CHAT,),
        rpm_limit=None,
        tpm_limit=None,
        store_full_messages=False,
        guardrail_enabled=True,
        is_system=True,
    )
    ctx = ProxyContext(
        team_id=tid,
        user_id=uid,
        vkey=vkey,
        capability=GatewayCapability.CHAT,
        request_id="rid",
        store_full_messages=False,
        guardrail_enabled=True,
    )
    uc = ProxyUseCase(db_session)
    meta = await uc._build_metadata(ctx, user_kwargs={"model": "bare-model"})
    assert "gateway_route_snapshot" not in meta


@pytest.mark.asyncio
async def test_platform_api_key_grant_policy_checks_model_and_capability(db_session: Any) -> None:
    tid = uuid.uuid4()
    uid = uuid.uuid4()
    ctx = ProxyContext(
        team_id=tid,
        user_id=uid,
        vkey=None,
        capability=GatewayCapability.EMBEDDING,
        request_id="rid",
        store_full_messages=False,
        guardrail_enabled=True,
        inbound_via="apikey",
        platform_api_key_id=uuid.uuid4(),
        platform_api_key_grant_id=uuid.uuid4(),
        allowed_models=("allowed-chat",),
        allowed_capabilities=(GatewayCapability.CHAT,),
    )
    uc = ProxyUseCase(db_session)

    with pytest.raises(ModelNotAllowedError):
        uc._check_model("other-model", ctx)

    with pytest.raises(CapabilityNotAllowedError):
        uc._check_capability(ctx)
