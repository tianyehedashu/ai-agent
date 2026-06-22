"""compute_chat_readiness 单元测试：聚焦 needs_connectivity_fix 分档可达性。"""

from __future__ import annotations

import uuid

import pytest

from domains.gateway.application import chat_model_selector_reads as reads
from domains.gateway.application.billing_context import BillingContext


class _FakeCatalog:
    """仅实现 readiness 计算所需的两个方法。"""

    def __init__(self, *, requestable: frozenset[str], registered_text: int) -> None:
        self._requestable = requestable
        self._registered_text = registered_text

    async def list_requestable_text_model_ids(self, *, billing_team_id, user_id=None):
        _ = billing_team_id, user_id
        return self._requestable

    async def count_registered_text_models(self, *, billing_team_id, user_id=None):
        _ = billing_team_id, user_id
        return self._registered_text


@pytest.mark.unit
@pytest.mark.asyncio
async def test_readiness_connectivity_fix_when_models_registered_but_unrequestable(monkeypatch):
    """已注册模型全部连通性失败时应落到 needs_connectivity_fix 而非 needs_model。"""
    monkeypatch.setattr(reads, "count_active_credentials_for_team", _fake_active_creds(1))
    billing = BillingContext(team_id=uuid.uuid4(), user_id=uuid.uuid4())
    catalog = _FakeCatalog(requestable=frozenset(), registered_text=2)

    readiness = await reads.compute_chat_readiness(object(), catalog, billing=billing)

    assert readiness == "needs_connectivity_fix"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_readiness_needs_model_when_no_registered_models(monkeypatch):
    monkeypatch.setattr(reads, "count_active_credentials_for_team", _fake_active_creds(1))
    billing = BillingContext(team_id=uuid.uuid4(), user_id=uuid.uuid4())
    catalog = _FakeCatalog(requestable=frozenset(), registered_text=0)

    readiness = await reads.compute_chat_readiness(object(), catalog, billing=billing)

    assert readiness == "needs_model"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_readiness_ready_when_requestable(monkeypatch):
    monkeypatch.setattr(reads, "count_active_credentials_for_team", _fake_active_creds(1))
    billing = BillingContext(team_id=uuid.uuid4(), user_id=uuid.uuid4())
    catalog = _FakeCatalog(requestable=frozenset(["m"]), registered_text=1)

    readiness = await reads.compute_chat_readiness(object(), catalog, billing=billing)

    assert readiness == "ready"


def _fake_active_creds(count: int):
    async def _impl(_session, _team_id):
        return count

    return _impl
