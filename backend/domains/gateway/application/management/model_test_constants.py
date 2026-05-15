"""Gateway 模型管理面「测试连通性」支持的 capability。

与 ``GatewayManagementWriteService.test_gateway_model`` 中 LiteLLM 直连探活
分支一致。变更时需同步前端 ``GATEWAY_MODEL_TEST_SUPPORTED_CAPABILITIES``
（``frontend/src/api/gateway.ts`` 中 ``GATEWAY_MODEL_TEST_SUPPORTED_CAPABILITIES``）。
"""

GATEWAY_MODEL_TEST_SUPPORTED_CAPABILITIES: frozenset[str] = frozenset(
    {"chat", "embedding", "image"}
)
