"""``model_test_constants`` 与探活分支约定一致。"""

from domains.gateway.application.management.model_test_constants import (
    GATEWAY_MODEL_TEST_SUPPORTED_CAPABILITIES,
)


def test_gateway_model_test_supported_capabilities_contract() -> None:
    """变更 capability 时需同步 ``writes.test_gateway_model`` 与前端 ``gateway.ts``。"""
    assert frozenset({"chat", "embedding", "image"}) == GATEWAY_MODEL_TEST_SUPPORTED_CAPABILITIES
