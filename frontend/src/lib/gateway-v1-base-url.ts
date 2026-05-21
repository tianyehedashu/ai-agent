/**
 * OpenAI 兼容网关根路径（/api/v1/openai/v1/*）
 *
 * 与管理 API（/api/v1/gateway/*）不同；开发环境 Vite 代理 /api 或 APP_ROOT。
 */

import { APP_ROOT, GATEWAY_OPENAI_V1_BASE } from '@/api/paths'

/** 解析当前环境下的 Gateway OpenAI 兼容 Base URL（含 /v1 后缀）。 */
export function resolveGatewayV1BaseUrl(): string {
  const configured = (import.meta.env.VITE_API_URL as string | undefined)?.trim()
  if (configured) {
    try {
      const origin = new URL(configured).origin
      return `${origin}${GATEWAY_OPENAI_V1_BASE}`
    } catch {
      const base = configured.replace(/\/$/, '')
      return base.endsWith(GATEWAY_OPENAI_V1_BASE) ? base : `${base}${GATEWAY_OPENAI_V1_BASE}`
    }
  }
  // 未配置 VITE_API_URL：走当前页面 origin（开发经 Vite /api 代理，生产同域 nginx）
  if (typeof window !== 'undefined') {
    return `${window.location.origin}${GATEWAY_OPENAI_V1_BASE}`
  }
  if (import.meta.env.DEV) {
    return `http://localhost:8000${GATEWAY_OPENAI_V1_BASE}`
  }
  return `https://your-api-host${APP_ROOT}/api/v1/openai/v1`
}

/** Anthropic SDK base_url（无 /v1 尾段） */
export function resolveGatewayAnthropicBaseUrl(): string {
  const openaiBase = resolveGatewayV1BaseUrl()
  return openaiBase.replace(/\/openai\/v1\/?$/, '/anthropic')
}
