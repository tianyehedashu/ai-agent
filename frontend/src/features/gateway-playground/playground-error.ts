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

const REFERENCE_IMAGE_PAYLOAD_HINT =
  '参考图若为内联 data URL 会显著增大请求体。请改用「上传」将大图传到图床，或压缩后再试。'

function isPayloadTooLargeError(error: PlaygroundError): boolean {
  if (error.httpStatus === 413) return true
  const blob = `${error.message} ${error.code ?? ''}`.toLowerCase()
  return /payload too large|entity too large|request entity|body too large|413/.test(blob)
}

/** 参考图模式下，413 等请求体过大错误附加可操作提示 */
export function withReferenceImagePayloadHint(
  error: PlaygroundError | null,
  referenceImageUrl?: string
): PlaygroundError | null {
  if (!error || !isPayloadTooLargeError(error)) return error
  const ref = referenceImageUrl?.trim() ?? ''
  if (!ref) return error

  const hint =
    ref.startsWith('data:') || ref.length > 200_000
      ? REFERENCE_IMAGE_PAYLOAD_HINT
      : '请求体过大，请缩短消息或减小参考图体积后再试。'

  if (error.hint?.includes('参考图') || error.hint?.includes('请求体过大')) {
    return error
  }

  return {
    ...error,
    hint: error.hint ? `${error.hint}\n${hint}` : hint,
  }
}
