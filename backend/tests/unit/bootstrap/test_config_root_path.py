"""Settings.root_path 规范化测试。"""

from __future__ import annotations

import pytest

from bootstrap.config import Settings, get_settings
from libs.api.paths import api_v1_path, service_path


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.unit
def test_root_path_strips_leading_and_trailing_whitespace() -> None:
    settings = Settings(root_path=" /ai-agent ")
    assert settings.root_path == "/ai-agent"


@pytest.mark.unit
def test_root_path_strips_trailing_space_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """K8s Secret 误写 ``/ai-agent `` 时须与 Nginx 请求路径一致。"""
    monkeypatch.setenv("ROOT_PATH", "/ai-agent ")
    settings = get_settings()
    assert settings.root_path == "/ai-agent"
    assert api_v1_path("auth", "me") == "/ai-agent/api/v1/auth/me"
    assert service_path("health") == "/ai-agent/health"


@pytest.mark.unit
def test_root_path_empty_string_after_strip() -> None:
    settings = Settings(root_path="   ")
    assert settings.root_path == ""
