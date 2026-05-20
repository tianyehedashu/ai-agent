/**
 * FastAPI / OpenAI 兼容错误体 ``detail`` 字段解析（api client、试调、Gateway 管理面共用）。
 */

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

/** 从 FastAPI ``detail``（string | array | object）提取可读消息。 */
export function parseFastApiDetail(detail: unknown): string | null {
  if (typeof detail === 'string') {
    const trimmed = detail.trim()
    return trimmed.length > 0 ? trimmed : null
  }
  if (Array.isArray(detail)) {
    const parts = detail
      .map((item) => {
        if (!isRecord(item)) return null
        const msg = item.msg ?? item.message
        if (typeof msg === 'string' && msg.trim().length > 0) {
          return msg.trim()
        }
        return null
      })
      .filter((part): part is string => part !== null)
    return parts.length > 0 ? parts.join('；') : null
  }
  if (isRecord(detail)) {
    if (isRecord(detail.error) && typeof detail.error.message === 'string') {
      const trimmed = detail.error.message.trim()
      if (trimmed.length > 0) return trimmed
    }
    if (typeof detail.message === 'string') {
      const trimmed = detail.message.trim()
      if (trimmed.length > 0) return trimmed
    }
  }
  return null
}

/** 从 fetch 响应 JSON 解析 ``detail`` 字段。 */
export function messageFromApiErrorBody(body: unknown, fallback: string): string {
  if (!isRecord(body) || !('detail' in body)) return fallback
  return parseFastApiDetail(body.detail) ?? fallback
}
