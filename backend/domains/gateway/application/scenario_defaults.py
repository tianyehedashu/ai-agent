"""场景默认模型：环境变量优先，Gateway 可见目录兜底。"""

from __future__ import annotations

from bootstrap.config import settings
from domains.gateway.application.internal_bridge_actor import resolve_internal_gateway_team_id
from domains.gateway.application.model_catalog_port import ModelCatalogPort
from domains.gateway.domain.scenario_defaults_policy import (
    ScenarioName,
    catalog_model_type_for_scenario,
    pick_scenario_from_visible,
)
from libs.exceptions import ValidationError

_SCENARIO_SETTINGS_ATTR: dict[ScenarioName, str] = {
    "default": "default_model",
    "fast": "fast_model",
    "reasoning": "reasoning_model",
    "code": "code_model",
    "long_context": "long_context_model",
    "vision": "vision_model",
    "embedding": "embedding_model",
}

_NO_MODEL_MESSAGES: dict[ScenarioName, str] = {
    "default": "无可用文本模型。请配置 DEFAULT_MODEL 或执行 make seed-gateway 同步目录。",
    "fast": "无可用快速模型。请配置 FAST_MODEL 或同步 Gateway 目录。",
    "reasoning": "无可用推理模型。请配置 REASONING_MODEL 或同步 Gateway 目录。",
    "code": "无可用代码模型。请配置 CODE_MODEL 或同步 Gateway 目录。",
    "long_context": "无可用长上下文模型。请配置 LONG_CONTEXT_MODEL 或同步 Gateway 目录。",
    "vision": "无可用视觉模型。请配置 VISION_MODEL 或同步 Gateway 目录。",
    "embedding": "无可用 Embedding 模型。请配置 EMBEDDING_MODEL 或同步 Gateway 目录。",
}


def _env_override_for(scenario: ScenarioName, env_override: str | None) -> str:
    if env_override is not None:
        return env_override.strip()
    return str(getattr(settings, _SCENARIO_SETTINGS_ATTR[scenario], "") or "").strip()


async def resolve_scenario_default(
    catalog: ModelCatalogPort,
    *,
    scenario: ScenarioName,
    env_override: str | None = None,
) -> str | None:
    """解析场景默认模型：env 优先且在可见列表则使用，否则取可见列表首个。"""
    override = _env_override_for(scenario, env_override)

    if scenario == "embedding":
        if override:
            return override
        team_id = resolve_internal_gateway_team_id()
        items = await catalog.list_visible_models(billing_team_id=team_id, model_type=None)
        for item in items:
            types = item.get("model_types") or []
            if "embedding" in types:
                model_id = item.get("id")
                if isinstance(model_id, str) and model_id.strip():
                    return model_id.strip()
        return None

    model_type = catalog_model_type_for_scenario(scenario)
    if model_type is None:
        return override or None

    team_id = resolve_internal_gateway_team_id()
    items = await catalog.list_visible_models(
        billing_team_id=team_id,
        model_type=model_type,
    )
    visible = frozenset(str(m["id"]) for m in items if m.get("id") is not None)
    return pick_scenario_from_visible(env_override=override, visible_ids=visible)


async def require_scenario_default(
    catalog: ModelCatalogPort,
    *,
    scenario: ScenarioName,
    env_override: str | None = None,
    empty_message: str | None = None,
) -> str:
    """同 ``resolve_scenario_default``，无结果时抛 ``ValidationError``。"""
    resolved = await resolve_scenario_default(
        catalog,
        scenario=scenario,
        env_override=env_override,
    )
    if resolved:
        return resolved
    raise ValidationError(empty_message or _NO_MODEL_MESSAGES[scenario])


class ScenarioDefaultsService:
    """场景默认模型解析（注入 ``ModelCatalogPort``）。"""

    def __init__(self, catalog: ModelCatalogPort) -> None:
        self._catalog = catalog

    async def resolve(
        self,
        scenario: ScenarioName,
        *,
        env_override: str | None = None,
    ) -> str | None:
        return await resolve_scenario_default(
            self._catalog,
            scenario=scenario,
            env_override=env_override,
        )

    async def require(
        self,
        scenario: ScenarioName,
        *,
        env_override: str | None = None,
        empty_message: str | None = None,
    ) -> str:
        return await require_scenario_default(
            self._catalog,
            scenario=scenario,
            env_override=env_override,
            empty_message=empty_message,
        )

    async def resolve_default(self, env_override: str | None = None) -> str | None:
        return await self.resolve("default", env_override=env_override)

    async def resolve_fast(self, env_override: str | None = None) -> str | None:
        return await self.resolve("fast", env_override=env_override)

    async def resolve_vision(self, env_override: str | None = None) -> str | None:
        return await self.resolve("vision", env_override=env_override)


__all__ = [
    "ScenarioDefaultsService",
    "ScenarioName",
    "require_scenario_default",
    "resolve_scenario_default",
]
