"""Gateway 单元测试共享 fixture。

``sync_gateway_catalog_from_seed`` / ``system_provider_credentials`` 等全局表写入
在 xdist 多 worker 共享同一 PostgreSQL 测试库时易死锁或交叉污染；
``loadgroup`` + 本组标记使同组用例串行于同一 worker。
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.xdist_group("gateway_db")


@pytest.fixture(autouse=True)
def _restore_litellm_register_model_after_test() -> None:
    """防止单测直接赋值 ``litellm.register_model`` 污染后续集成测。"""
    import litellm

    original = litellm.register_model
    yield
    if litellm.register_model is not original:
        litellm.register_model = original
