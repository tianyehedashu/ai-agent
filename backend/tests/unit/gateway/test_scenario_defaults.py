"""ScenarioDefaultsService 单元测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from domains.gateway.application.catalog.scenario_defaults import (
    ScenarioDefaultsService,
    require_scenario_default,
    resolve_scenario_default,
)
from libs.exceptions import ValidationError


class _FakeCatalog:
    def __init__(self, items: list[dict[str, object]]) -> None:
        self._items = items

    async def list_visible_models(self, *, billing_team_id, model_type, user_id=None, **_kw):
        _ = billing_team_id, user_id
        if model_type is None:
            return self._items
        return [i for i in self._items if model_type in (i.get("model_types") or [])]

    async def list_personal_models_for_selector(self, user_id, model_type, provider=None):
        _ = user_id, model_type, provider
        return []

    async def list_requestable_text_model_ids(self, *, billing_team_id, user_id=None):
        items = await self.list_visible_models(
            billing_team_id=billing_team_id,
            model_type="text",
            user_id=user_id,
        )
        return frozenset(str(i["id"]) for i in items if i.get("id") is not None)

    async def resolve_chat_default_text_model(self, *, billing_team_id, user_id=None):
        from bootstrap.config import settings
        from domains.gateway.domain.catalog.scenario_defaults_policy import pick_scenario_from_visible

        items = await self.list_visible_models(
            billing_team_id=billing_team_id,
            model_type="text",
            user_id=user_id,
        )
        visible = frozenset(str(i["id"]) for i in items if i.get("id") is not None)
        return pick_scenario_from_visible(
            env_override=settings.default_model,
            visible_ids=visible,
        )


@pytest.mark.asyncio
async def test_resolve_scenario_default_env_valid(monkeypatch) -> None:
    monkeypatch.setattr(
        "domains.gateway.application.catalog.scenario_defaults.settings.default_model", "m-a"
    )
    catalog = _FakeCatalog(
        [
            {"id": "m-a", "model_types": ["text"]},
            {"id": "m-b", "model_types": ["text"]},
        ]
    )
    assert await resolve_scenario_default(catalog, scenario="default") == "m-a"


@pytest.mark.asyncio
async def test_resolve_scenario_default_env_invalid_falls_back_first(monkeypatch) -> None:
    monkeypatch.setattr(
        "domains.gateway.application.catalog.scenario_defaults.settings.default_model", "missing"
    )
    catalog = _FakeCatalog(
        [
            {"id": "m-first", "model_types": ["text"]},
            {"id": "m-second", "model_types": ["text"]},
        ]
    )
    assert await resolve_scenario_default(catalog, scenario="default") == "m-first"


@pytest.mark.asyncio
async def test_require_scenario_default_raises_when_empty() -> None:
    catalog = _FakeCatalog([])
    with pytest.raises(ValidationError, match="无可用文本模型"):
        await require_scenario_default(catalog, scenario="default")


@pytest.mark.asyncio
async def test_scenario_defaults_service_fast() -> None:
    catalog = AsyncMock()
    catalog.list_visible_models.return_value = [{"id": "fast-1", "model_types": ["text"]}]
    svc = ScenarioDefaultsService(catalog)
    assert await svc.resolve_fast("unknown") == "fast-1"
