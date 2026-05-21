/**
 * Playground 请求体构建与展示用脱敏（纯函数，便于单测）
 */

import type { PlaygroundApiFlavor } from './types'

export interface BuildPlaygroundRequestBodyParams {
  model: string
  prompt: string
  stream: boolean
  flavor: PlaygroundApiFlavor
  maxTokens?: number
  /** DashScope Qwen3：extra_body.enable_thinking；开启时建议 stream */
  enableThinking?: boolean
  /** Anthropic Extended Thinking */
  anthropicThinkingBudgetTokens?: number
}

const DEFAULT_ANTHROPIC_MAX_TOKENS = 1024

export function buildPlaygroundRequestBody(
  params: BuildPlaygroundRequestBodyParams
): Record<string, unknown> {
  if (params.flavor === 'anthropic') {
    const body: Record<string, unknown> = {
      model: params.model,
      max_tokens: params.maxTokens ?? DEFAULT_ANTHROPIC_MAX_TOKENS,
      stream: params.stream,
      messages: [{ role: 'user', content: params.prompt }],
    }
    if (params.enableThinking) {
      body.thinking = {
        type: 'enabled',
        budget_tokens: params.anthropicThinkingBudgetTokens ?? 8000,
      }
    }
    return body
  }
  const body: Record<string, unknown> = {
    model: params.model,
    stream: params.stream,
    messages: [{ role: 'user', content: params.prompt }],
  }
  if (params.enableThinking) {
    body.extra_body = { enable_thinking: true }
  }
  return body
}

export interface BuildVisionRequestBodyParams {
  model: string
  prompt: string
  imageUrl: string
  stream: boolean
}

/** OpenAI Chat 多模态（视觉理解） */
export function buildVisionRequestBody(
  params: BuildVisionRequestBodyParams
): Record<string, unknown> {
  return {
    model: params.model,
    stream: params.stream,
    messages: [
      {
        role: 'user',
        content: [
          { type: 'text', text: params.prompt },
          { type: 'image_url', image_url: { url: params.imageUrl } },
        ],
      },
    ],
  }
}

export interface BuildImageGenRequestBodyParams {
  model: string
  prompt: string
  size?: string
  n?: number
  responseFormat?: 'url' | 'b64_json'
}

export function buildImageGenRequestBody(
  params: BuildImageGenRequestBodyParams
): Record<string, unknown> {
  const body: Record<string, unknown> = {
    model: params.model,
    prompt: params.prompt,
    n: params.n ?? 1,
  }
  if (params.size) body.size = params.size
  if (params.responseFormat) body.response_format = params.responseFormat
  return body
}

export interface BuildVideoGenRequestBodyParams {
  model: string
  prompt: string
  imageUrl?: string
}

export function buildVideoGenRequestBody(
  params: BuildVideoGenRequestBodyParams
): Record<string, unknown> {
  const body: Record<string, unknown> = {
    model: params.model,
    prompt: params.prompt,
  }
  if (params.imageUrl?.trim()) {
    body.image = params.imageUrl.trim()
  }
  return body
}

export function maskTokenForDisplay(token: string): string {
  if (token.length <= 12) return '***'
  return `${token.slice(0, 8)}...***`
}

export function maskAuthHeadersForDisplay(headers: Record<string, string>): Record<string, string> {
  const out = { ...headers }
  if (out.Authorization) {
    const token = out.Authorization.replace(/^Bearer\s+/i, '')
    out.Authorization = `Bearer ${maskTokenForDisplay(token)}`
  }
  if (out['x-api-key']) {
    out['x-api-key'] = maskTokenForDisplay(out['x-api-key'])
  }
  return out
}
