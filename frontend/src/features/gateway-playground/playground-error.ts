import { parseFastApiDetail } from '@/lib/fastapi-error-detail'

import { extractAnthropicError, type AnthropicErrorEnvelope } from './anthropic-sse'
import { extractOpenAiCompatError, type OpenAiCompatChunk } from './openai-sse'

import type { PlaygroundApiFlavor, PlaygroundError } from './types'

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function parseDetailCode(detail: unknown): string | null {
  if (!isRecord(detail)) return null
  if (isRecord(detail.error)) {
    const code = detail.error.type ?? detail.error.code
    if (typeof code === 'string' && code.trim().length > 0) {
      return code.trim()
    }
  }
  return null
}

/** 解析 HTTP 非 2xx 响应体（兼容 FastAPI detail 与 OpenAI / Anthropic 原生错误）。 */
export function extractPlaygroundHttpError(
  json: unknown,
  httpStatus: number,
  fallback: string,
  flavor: PlaygroundApiFlavor
): PlaygroundError {
  if (isRecord(json) && 'detail' in json) {
    const detail = json.detail
    const detailMessage = parseFastApiDetail(detail)
    if (detailMessage) {
      return {
        httpStatus,
        code: parseDetailCode(detail),
        message: detailMessage,
      }
    }
    if (isRecord(detail)) {
      if (flavor === 'anthropic') {
        return extractAnthropicError(detail as AnthropicErrorEnvelope, httpStatus, fallback)
      }
      if (isRecord(detail.error)) {
        return extractOpenAiCompatError(
          { error: detail.error } as OpenAiCompatChunk,
          httpStatus,
          fallback
        )
      }
    }
  }

  if (flavor === 'anthropic') {
    return extractAnthropicError(json as AnthropicErrorEnvelope | null, httpStatus, fallback)
  }
  return extractOpenAiCompatError(json as OpenAiCompatChunk | null, httpStatus, fallback)
}

export async function readPlaygroundErrorBody(response: Response): Promise<unknown> {
  const bodyText = await response.text()
  if (bodyText.trim().length === 0) return null
  try {
    return JSON.parse(bodyText) as unknown
  } catch {
    return { detail: bodyText.trim() }
  }
}

export function buildNetworkPlaygroundError(error: unknown, url: string): PlaygroundError {
  const browserMessage = error instanceof Error ? error.message : '网络请求失败'
  return {
    message: browserMessage,
    hint: `无法连接到 ${url}。请确认后端服务可用、OpenAI 兼容面路径为 /api/v1/openai/v1/*（或部署时配置 VITE_API_URL / VITE_APP_ROOT）；若浏览器控制台提示 CORS，请检查跨域配置。`,
  }
}
