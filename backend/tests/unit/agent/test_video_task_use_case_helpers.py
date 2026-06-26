"""video_task_use_case 纯函数与取消语义。"""

from __future__ import annotations

from domains.agent.application.video_task_use_case import (
    _extract_video_url,
    _is_volcengine_video_still_processing,
)


def test_extract_video_url_openai_shape() -> None:
    assert _extract_video_url({"video": {"url": "https://example.com/a.mp4"}}) == (
        "https://example.com/a.mp4"
    )


def test_extract_video_url_volcengine_content_shape() -> None:
    assert _extract_video_url(
        {"content": {"video_url": "https://example.com/b.mp4"}, "status": "succeeded"}
    ) == "https://example.com/b.mp4"


def test_is_volcengine_video_still_processing_when_queued_without_url() -> None:
    assert _is_volcengine_video_still_processing({"id": "cgt-1", "status": "queued"}) is True


def test_is_volcengine_video_not_processing_when_url_present() -> None:
    assert (
        _is_volcengine_video_still_processing(
            {"status": "succeeded", "video": {"url": "https://example.com/x.mp4"}}
        )
        is False
    )
