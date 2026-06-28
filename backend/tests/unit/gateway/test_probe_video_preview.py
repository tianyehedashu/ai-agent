"""``probe_video_preview`` 纯函数单测。"""

from domains.gateway.application.catalog.management.probe_video_preview import (
    video_generation_probe_preview,
)


def test_video_generation_probe_preview_from_object() -> None:
    resp = type("VideoResp", (), {"id": "video_abc123", "status": "queued"})()
    assert video_generation_probe_preview(resp) == "queued: video_abc123"


def test_video_generation_probe_preview_from_dict() -> None:
    assert video_generation_probe_preview({"id": "vid-1", "status": "processing"}) == (
        "processing: vid-1"
    )


def test_video_generation_probe_preview_id_only() -> None:
    assert video_generation_probe_preview({"id": "vid-only"}) == "vid-only"


def test_video_generation_probe_preview_empty() -> None:
    assert video_generation_probe_preview({}) == ""
