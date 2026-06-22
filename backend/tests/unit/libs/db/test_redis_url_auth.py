"""``build_authenticated_redis_url`` 回归测试。

阿里云 Redis 启用 ACL 后必须 username+password 鉴权；LiteLLM Router 仅接受
redis_url 字符串，须把凭据注入 URL，否则连接被拒为 WRONGPASS、熔断打开。
"""

import pytest

from libs.db import redis as redis_module
from libs.db.redis import build_authenticated_redis_url


@pytest.fixture
def _creds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(redis_module.settings, "redis_username", "acl_user", raising=False)
    monkeypatch.setattr(redis_module.settings, "redis_password", "p@ss/word", raising=False)


def test_injects_username_and_password_url_encoded(_creds: None) -> None:
    url = build_authenticated_redis_url("redis://redis.example.com:6379/0")
    assert url == "redis://acl_user:p%40ss%2Fword@redis.example.com:6379/0"


def test_preserves_existing_credentials(_creds: None) -> None:
    base = "redis://other:secret@redis.example.com:6379/0"
    assert build_authenticated_redis_url(base) == base


def test_noop_without_configured_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(redis_module.settings, "redis_username", None, raising=False)
    monkeypatch.setattr(redis_module.settings, "redis_password", None, raising=False)
    base = "redis://redis.example.com:6379/0"
    assert build_authenticated_redis_url(base) == base


def test_keeps_db_index_and_default_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(redis_module.settings, "redis_username", None, raising=False)
    monkeypatch.setattr(redis_module.settings, "redis_password", "only-pass", raising=False)
    url = build_authenticated_redis_url("redis://redis.example.com/2")
    assert url == "redis://:only-pass@redis.example.com/2"
