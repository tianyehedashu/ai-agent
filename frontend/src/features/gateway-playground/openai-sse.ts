/**
 * OpenAI 兼容 SSE / 错误体解析（纯函数，可单测）
 */

import type { PlaygroundError } from './types'

interface ChatChunkDelta {
  content?: string | null
  reasoning_content?: string | null
  finish_reason?: string | null
}

interface ChatChoice {
  delta?: ChatChunkDelta
  message?: { content?: string | null; reasoning_content?: string | null }
  finish_reason?: string | null
}

export interface OpenAiCompatChunk {
  id?: string
  choices?: ChatChoice[]
  usage?: {
    prompt_tokens?: number
    completion_tokens?: number
    total_tokens?: number
  }
  /** 网关 / LiteLLM 在末帧或非流式响应中注入（USD） */
  response_cost?: number
  error?: { message?: string; code?: string | null; type?: string | null }
}

export function extractResponseCostUsd(chunk: OpenAiCompatChunk | null): number | undefined {
  if (chunk === null) return undefined
  const raw = chunk.response_cost
  if (typeof raw === 'number' && Number.isFinite(raw) && raw >= 0) {
    return raw
  }
  return undefined
}

export interface ParseSseResult {
  chunks: OpenAiCompatChunk[]
  rest: string
  done: boolean
}

/** 解析 SSE 缓冲：返回已完整事件块中的 JSON chunk（不含 `[DONE]`）。 */
export function parseOpenAiSseBuffer(buffer: string): ParseSseResult {
  const chunks: OpenAiCompatChunk[] = []
  let rest = buffer
  let done = false
  let sep = rest.indexOf('\n\n')
  while (sep !== -1) {
    const block = rest.slice(0, sep)
    rest = rest.slice(sep + 2)
    for (const line of block.split('\n')) {
      const trimmed = line.trim()
      if (!trimmed.startsWith('data:')) continue
      const payload = trimmed.slice(5).trim()
      if (payload === '[DONE]') {
        done = true
        continue
      }
      try {
        chunks.push(JSON.parse(payload) as OpenAiCompatChunk)
      } catch {
        // 忽略非 JSON 行（注释 / 心跳）
      }
    }
    sep = rest.indexOf('\n\n')
  }
  return { chunks, rest, done }
}

/** 从单帧 OpenAI 兼容 chunk 提取正文与思考增量。 */
export function extractOpenAiStreamTextParts(chunk: OpenAiCompatChunk): {
  content: string
  reasoning: string
} {
  const delta = chunk.choices?.[0]?.delta
  const content = typeof delta?.content === 'string' ? delta.content : ''
  const reasoning = typeof delta?.reasoning_content === 'string' ? delta.reasoning_content : ''
  return { content, reasoning }
}

export function extractOpenAiCompatError(
  json: OpenAiCompatChunk | null,
  httpStatus: number,
  fallback: string
): PlaygroundError {
  const err = json?.error
  const trimmed = err?.message?.trim()
  return {
    httpStatus,
    code: err?.code ?? err?.type ?? null,
    message: trimmed && trimmed.length > 0 ? trimmed : fallback,
  }
}
