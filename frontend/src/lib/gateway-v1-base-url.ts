/**
 * OpenAI 兼容网关根路径（/v1/*）
 *
 * 与管理 API（/api/v1/gateway/*）不同；开发环境 Vite 仅代理 /api，直连后端需用 8000。
 */

/** 解析当前环境下的 Gateway OpenAI 兼容 Base URL（含 /v1 后缀）。 */
export function resolveGatewayV1BaseUrl(): string {
  const configured = (import.meta.env.VITE_API_URL as string | undefined)?.trim()
  if (configured) {
    try {
      const origin = new URL(configured).origin
      return `${origin}/v1`
    } catch {
      return `${configured.replace(/\/$/, '')}/v1`
    }
  }
  if (import.meta.env.DEV) {
    return 'http://localhost:8000/v1'
  }
  if (typeof window !== 'undefined') {
    return `${window.location.origin}/v1`
  }
  return 'https://your-api-host/v1'
}
