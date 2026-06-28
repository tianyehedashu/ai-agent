"""``build_volcengine_video_create_request`` 纯函数行为。"""

from __future__ import annotations

from domains.gateway.domain.provider.volcengine_video import (
    DEFAULT_VOLCENGINE_API_BASE,
    build_volcengine_video_create_request,
    map_volcengine_video_task_to_openai,
    normalize_volcengine_video_model,
    parse_video_duration_seconds,
)


def test_normalize_strips_volcengine_prefix() -> None:
    assert normalize_volcengine_video_model("volcengine/doubao-seedance-1-0-lite-t2v-250428") == (
        "doubao-seedance-1-0-lite-t2v-250428"
    )


def test_build_create_request_uses_real_model_and_duration() -> None:
    req = build_volcengine_video_create_request(
        api_key="sk-test",
        api_base="https://example.com/api/v3",
        model_id="doubao-seedance-1-0-lite-t2v-250428",
        prompt="ping",
        seconds="5",
    )
    assert req.url == "https://example.com/api/v3/contents/generations/tasks"
    assert req.auth_header == "Bearer sk-test"
    assert req.json_body["model"] == "doubao-seedance-1-0-lite-t2v-250428"
    assert req.json_body["duration"] == 5
    assert req.json_body["content"] == [{"type": "text", "text": "ping"}]
    assert req.json_body["watermark"] is False


def test_falls_back_to_default_api_base_when_none() -> None:
    req = build_volcengine_video_create_request(
        api_key="k",
        api_base=None,
        model_id="doubao-seedance-1-0-lite-t2v-250428",
        prompt="ping",
    )
    assert req.url.startswith(DEFAULT_VOLCENGINE_API_BASE)
    assert req.url.endswith("/contents/generations/tasks")


def test_parse_video_duration_seconds_defaults() -> None:
    assert parse_video_duration_seconds(None) == 5
    assert parse_video_duration_seconds("bad") == 5
    assert parse_video_duration_seconds("8") == 8


def test_map_volcengine_video_task_to_openai() -> None:
    mapped = map_volcengine_video_task_to_openai(
        {"id": "cgt-123", "status": "queued", "model": "doubao-seedance-1-0-lite-t2v-250428"},
        fallback_model="fallback-model",
    )
    assert mapped == {
        "id": "cgt-123",
        "object": "video",
        "status": "queued",
        "model": "doubao-seedance-1-0-lite-t2v-250428",
    }


def test_map_volcengine_video_task_includes_video_url_when_succeeded() -> None:
    mapped = map_volcengine_video_task_to_openai(
        {
            "id": "cgt-123",
            "status": "succeeded",
            "model": "doubao-seedance-1-0-lite-t2v-250428",
            "content": {"video_url": "https://example.com/out.mp4"},
        },
        fallback_model="fallback-model",
    )
    assert mapped["video"]["url"] == "https://example.com/out.mp4"
    assert mapped["url"] == "https://example.com/out.mp4"


def test_is_volcengine_video_terminal_status() -> None:
    from domains.gateway.domain.provider.volcengine_video import (
        is_volcengine_video_in_progress_status,
        is_volcengine_video_terminal_status,
    )

    assert is_volcengine_video_terminal_status("succeeded")
    assert is_volcengine_video_terminal_status("failed")
    assert not is_volcengine_video_terminal_status("running")
    assert is_volcengine_video_in_progress_status("queued")
    assert is_volcengine_video_in_progress_status("running")
