/**
 * AI Gateway API · 共享常量与基址
 *
 * - 团队资源：`/api/v1/gateway/teams/{teamId}/*`（路径显式选团队）
 * - 用户域：`/my-credentials`、`/my-models`、`/models/available` 无 team 路径
 */

import { GATEWAY_API_BASE } from '@/api/paths'

export { GATEWAY_API_BASE }

/** 团队 scoped 管理路径 */
export function teamGatewayPath(teamId: string, suffix: string): string {
  const normalized = suffix.startsWith('/') ? suffix : `/${suffix}`
  return `${GATEWAY_API_BASE}/teams/${teamId}${normalized}`
}

/**
 * 与 Python 端 ``GATEWAY_MODEL_TEST_SUPPORTED_CAPABILITIES`` 一致。
 * 用于决定一个 GatewayModel 是否支持「连通性测试」。
 */
export const GATEWAY_MODEL_TEST_SUPPORTED_CAPABILITIES = ['chat', 'embedding', 'image'] as const
