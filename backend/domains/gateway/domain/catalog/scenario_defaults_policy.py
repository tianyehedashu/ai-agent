"""场景默认模型选择策略（纯函数，无 IO）。"""

from __future__ import annotations

from typing import Literal

from .model_selection_policy import pick_configured_or_first_visible

ScenarioName = Literal[
    "default",
    "fast",
    "reasoning",
    "code",
    "long_context",
    "vision",
    "embedding",
]

_SCENARIO_CATALOG_MODEL_TYPE: dict[ScenarioName, str | None] = {
    "default": "text",
    "fast": "text",
    "reasoning": "text",
    "code": "text",
    "long_context": "text",
    "vision": "image",
    "embedding": None,
}


def catalog_model_type_for_scenario(scenario: ScenarioName) -> str | None:
    """场景对应的 Gateway 选择器 ``model_type``；``embedding`` 需按 capability 扫描。"""
    return _SCENARIO_CATALOG_MODEL_TYPE[scenario]


def pick_scenario_from_visible(
    *,
    env_override: str,
    visible_ids: frozenset[str],
) -> str | None:
    """env 非空且在可见集则使用，否则取可见集首个。"""
    return pick_configured_or_first_visible(env_override.strip(), visible_ids)


__all__ = [
    "ScenarioName",
    "catalog_model_type_for_scenario",
    "pick_scenario_from_visible",
]
