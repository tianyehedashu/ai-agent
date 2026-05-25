/**
 * FastAPI Problem Details / OpenAI 兼容错误体解析（api client、试调、Gateway 管理面共用）。
 */

import type { FieldError, ParsedApiError } from '@/api/errors'

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function parseFieldErrors(value: unknown): FieldError[] | undefined {
  if (!Array.isArray(value)) return undefined
  const items: FieldError[] = []
  for (const item of value) {
    if (!isRecord(item)) continue
    const msg = item.msg ?? item.message
    if (typeof msg !== 'string' || msg.trim().length === 0) continue
    const locRaw = item.loc
    const loc: (string | number)[] = Array.isArray(locRaw)
      ? locRaw.filter(
          (part): part is string | number => typeof part === 'string' || typeof part === 'number'
        )
      : []
    items.push({
      loc,
      msg: msg.trim(),
      type: typeof item.type === 'string' ? item.type : 'value_error',
    })
  }
  return items.length > 0 ? items : undefined
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

/** 解析错误响应 JSON（RFC 7807 + 旧 ``detail`` 形态）。 */
export function parseApiErrorBody(body: unknown, fallback: string): ParsedApiError {
  if (!isRecord(body)) {
    return { message: fallback }
  }

  const rfcDetail = typeof body.detail === 'string' ? body.detail.trim() : null
  const legacyDetail = rfcDetail ? null : parseFastApiDetail(body.detail)
  const message = rfcDetail ?? legacyDetail ?? fallback

  return {
    message,
    code: typeof body.code === 'string' ? body.code : undefined,
    title: typeof body.title === 'string' ? body.title : undefined,
    errors: parseFieldErrors(body.errors),
    extra: isRecord(body.extra) ? body.extra : undefined,
  }
}

/** 从 fetch 响应 JSON 解析 ``detail`` 字段（兼容旧调用方）。 */
export function messageFromApiErrorBody(body: unknown, fallback: string): string {
  return parseApiErrorBody(body, fallback).message
}
