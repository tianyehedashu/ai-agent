"""scenario_defaults_policy 纯函数单测。"""

from domains.gateway.domain.scenario_defaults_policy import (
    catalog_model_type_for_scenario,
    pick_scenario_from_visible,
)


def test_pick_scenario_from_visible_env_in_set() -> None:
    visible = frozenset({"m-a", "m-b"})
    assert pick_scenario_from_visible(env_override="m-a", visible_ids=visible) == "m-a"


def test_pick_scenario_from_visible_env_missing_uses_first() -> None:
    visible = frozenset({"m-first", "m-second"})
    assert pick_scenario_from_visible(env_override="missing", visible_ids=visible) == "m-first"


def test_catalog_model_type_for_scenario() -> None:
    assert catalog_model_type_for_scenario("vision") == "image"
    assert catalog_model_type_for_scenario("embedding") is None
