import { ApiError } from '@/api/client'

function validationItemMessage(item: unknown): string | null {
  if (typeof item !== 'object' || item === null) return null
  const rec = item as Record<string, unknown>
  if (typeof rec.msg === 'string') {
    const trimmed = rec.msg.trim()
    return trimmed.length > 0 ? trimmed : null
  }
  if (typeof rec.message === 'string') {
    const trimmed = rec.message.trim()
    return trimmed.length > 0 ? trimmed : null
  }
  return null
}

function parseFastApiDetail(detail: unknown): string | null {
  if (typeof detail === 'string') {
    const trimmed = detail.trim()
    return trimmed.length > 0 ? trimmed : null
  }
  if (Array.isArray(detail)) {
    const parts = detail
      .map((item) => validationItemMessage(item))
      .filter((part): part is string => part !== null)
    return parts.length > 0 ? parts.join('；') : null
  }
  if (typeof detail === 'object' && detail !== null) {
    if ('message' in detail && typeof detail.message === 'string') {
      const trimmed = detail.message.trim()
      if (trimmed.length > 0) return trimmed
    }
  }
  return null
}

/** 将 Gateway 管理 API 错误转为用户可读文案（试调 Key reveal 等）。 */
export function formatGatewayManagementError(error: Error): string {
  if (!(error instanceof ApiError)) {
    return error.message
  }
  const raw = error.message.trim()
  if (error.status === 404 && (raw === 'Not Found' || raw === 'Not found')) {
    return '接口不存在（404）。请确认后端已更新并重启；若 Key 已撤销或属于其他团队，请重新选择。'
  }
  if (error.status === 403) {
    return raw.length > 0 ? raw : '无权访问该资源（403）'
  }
  return raw.length > 0 ? raw : `请求失败（${String(error.status)}）`
}

/** 从 fetch 响应 JSON 解析 FastAPI ``detail`` 字段。 */
export function messageFromApiErrorBody(body: unknown, fallback: string): string {
  if (typeof body !== 'object' || body === null) return fallback
  if (!('detail' in body)) return fallback
  return parseFastApiDetail((body as { detail: unknown }).detail) ?? fallback
}
