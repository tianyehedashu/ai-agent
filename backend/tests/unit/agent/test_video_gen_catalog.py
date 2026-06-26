"""video_gen_catalog：时长解析（基于 Gateway model_type=video）。"""

from domains.agent.application.video_gen_catalog import (
    allowed_durations_for_video_model,
)


def test_allowed_durations_from_catalog_entry() -> None:
    catalog = [
        {"value": "custom-video", "durations": [7, 12]},
        {"value": "sora-2", "durations": [5, 10]},
    ]
    assert allowed_durations_for_video_model(catalog, "custom-video") == {7, 12}


def test_allowed_durations_fallback_default() -> None:
    # 无 video_durations tag 时统一回退到默认 {5, 10, 15}
    assert allowed_durations_for_video_model([], "any-model") == {5, 10, 15}


def test_allowed_durations_empty_entry_falls_back_to_default() -> None:
    catalog = [{"value": "sora-2", "durations": []}]
    assert allowed_durations_for_video_model(catalog, "sora-2") == {5, 10, 15}
