/**
 * HTTP 路径常量 — 与后端 ROOT_PATH + API_PREFIX 对齐。
 *
 * 未配置 VITE_APP_ROOT 时默认 `/ai-agent`；设为空字符串可部署在站点根路径。
 */

/** 默认服务级前缀（与 backend ROOT_PATH 默认一致） */
export const DEFAULT_APP_ROOT = '/ai-agent'

function resolveAppRoot(): string {
  const raw = import.meta.env.VITE_APP_ROOT as string | undefined
  if (raw === undefined) {
    return DEFAULT_APP_ROOT
  }
  return raw.replace(/\/$/, '')
}

/** 服务级前缀（不含尾斜杠） */
export const APP_ROOT = resolveAppRoot()

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
