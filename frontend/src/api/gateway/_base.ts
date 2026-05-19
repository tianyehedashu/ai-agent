/**
 * AI Gateway API · 共享常量与基址
 *
 * - 所有 /api/v1/gateway/* 请求路径前缀
 * - apiClient 会自动注入 X-Team-Id（来自 gateway-team store）
 */

/** Gateway 管理端点公共前缀 */
export const GATEWAY_API_BASE = '/api/v1/gateway'

/**
 * 与 Python 端 ``GATEWAY_MODEL_TEST_SUPPORTED_CAPABILITIES`` 一致。
 * 用于决定一个 GatewayModel 是否支持「连通性测试」。
 */
export const GATEWAY_MODEL_TEST_SUPPORTED_CAPABILITIES = ['chat', 'embedding', 'image'] as const
