/**
 * HTTP 路径常量 — 与后端 ROOT_PATH + API_PREFIX 对齐。
 *
 * 生产环境通过 VITE_APP_ROOT 配置服务级前缀（如 /ai-agent）。
 */

/** 服务级前缀（不含尾斜杠），默认空 */
export const APP_ROOT =
  (import.meta.env.VITE_APP_ROOT as string | undefined)?.replace(/\/$/, '') ?? ''

/** 管理 API 前缀：{APP_ROOT}/api/v1 */
export const API_V1 = `${APP_ROOT}/api/v1`

/** Gateway 管理面：{APP_ROOT}/api/v1/gateway */
export const GATEWAY_API_BASE = `${API_V1}/gateway`

/** OpenAI 兼容 SDK base_url（含 /v1 尾段） */
export const GATEWAY_OPENAI_V1_BASE = `${API_V1}/openai/v1`

/** Anthropic 兼容 SDK base_url（无 /v1 尾段） */
export const GATEWAY_ANTHROPIC_BASE = `${API_V1}/anthropic`

/** 拼接 API v1 子路径 */
export function apiV1Path(suffix: string): string {
  const normalized = suffix.startsWith('/') ? suffix : `/${suffix}`
  return `${API_V1}${normalized}`
}
