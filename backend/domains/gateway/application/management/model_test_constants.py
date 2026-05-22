"""Gateway 模型管理面「测试连通性」支持的 capability。

与 ``GatewayManagementWriteService.test_gateway_model`` 中 LiteLLM 直连探活
分支一致。变更时需同步前端 ``GATEWAY_MODEL_TEST_SUPPORTED_CAPABILITIES``
（``frontend/src/api/gateway/_base.ts``）。
"""

GATEWAY_MODEL_TEST_SUPPORTED_CAPABILITIES: frozenset[str] = frozenset(
    {"chat", "embedding", "image", "video_generation"}
)

# LiteLLM ``avideo_generation`` 默认 600s；探活仅等待任务提交/排队响应。
VIDEO_PROBE_TIMEOUT = 120
