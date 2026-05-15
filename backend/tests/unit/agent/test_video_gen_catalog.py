"""video_gen_catalog：时长解析与内置目录。"""

from domains.agent.application.video_gen_catalog import (
    allowed_durations_for_video_model,
    list_builtin_video_models,
)


def test_list_builtin_contains_sora() -> None:
    ids = {x["value"] for x in list_builtin_video_models()}
    assert "openai::sora1.0" in ids
    assert "openai::sora2.0" in ids


def test_allowed_durations_from_catalog_entry() -> None:
    catalog = [
        {"value": "custom::x", "durations": [7, 12]},
        {"value": "openai::sora1.0", "durations": [5, 10]},
    ]
    assert allowed_durations_for_video_model(catalog, "custom::x") == {7, 12}


def test_allowed_durations_fallback_sora1() -> None:
    assert allowed_durations_for_video_model([], "openai::sora1.0") == {5, 10, 15, 20}


def test_allowed_durations_fallback_other() -> None:
    assert allowed_durations_for_video_model([], "vendor::foo") == {5, 10, 15}
