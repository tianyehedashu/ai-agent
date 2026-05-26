"""火山直连 provider 判定。"""

from __future__ import annotations

from domains.gateway.domain.policies.volcengine_direct import should_use_volcengine_direct_upstream
from domains.gateway.domain.policies.volcengine_image import should_use_volcengine_direct_image
from domains.gateway.domain.policies.volcengine_video import should_use_volcengine_direct_video


def test_should_use_volcengine_direct_upstream() -> None:
    assert should_use_volcengine_direct_upstream("volcengine") is True
    assert should_use_volcengine_direct_upstream("Volcengine") is True
    assert should_use_volcengine_direct_upstream("openai") is False


def test_image_and_video_delegate_to_upstream() -> None:
    assert should_use_volcengine_direct_image("volcengine") is True
    assert should_use_volcengine_direct_video("volcengine") is True
    assert should_use_volcengine_direct_image("openai") is False
