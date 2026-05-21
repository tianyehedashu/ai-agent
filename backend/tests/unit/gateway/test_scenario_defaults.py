"""ScenarioDefaultsService 单元测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from domains.gateway.application.scenario_defaults import (
    ScenarioDefaultsService,
    require_scenario_default,
    resolve_scenario_default,
)
from libs.exceptions import ValidationError


class _FakeCatalog:
    def __init__(self, items: list[dict[str, object]]) -> None:
        self._items = items

    async def list_visible_models(self, *, billing_team_id, model_type):  # noqa: ANN001
        _ = billing_team_id
        if model_type is None:
            return self._items
        return [i for i in self._items if model_type in (i.get("model_types") or [])]


@pytest.mark.asyncio
async def test_resolve_scenario_default_env_valid(monkeypatch) -> None:
    monkeypatch.setattr("domains.gateway.application.scenario_defaults.settings.default_model", "m-a")
    catalog = _FakeCatalog(
        [
            {"id": "m-a", "model_types": ["text"]},
            {"id": "m-b", "model_types": ["text"]},
        ]
    )
    assert await resolve_scenario_default(catalog, scenario="default") == "m-a"


@pytest.mark.asyncio
async def test_resolve_scenario_default_env_invalid_falls_back_first(monkeypatch) -> None:
    monkeypatch.setattr("domains.gateway.application.scenario_defaults.settings.default_model", "missing")
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
