/**
 * Anthropic Messages 兼容 SSE / 响应 / 错误体解析（纯函数，可单测）
 *
 * Anthropic SSE 形如：
 *   event: <name>\ndata: <json>\n\n
 * 其中以 `message_stop` 事件作为结束信号（不存在 `[DONE]`）。
 */

import type { PlaygroundError } from './types'

export interface AnthropicContentBlock {
  type: string
  text?: string
}

export interface AnthropicMessage {
  id?: string
  type?: 'message'
  role?: 'assistant'
  model?: string
  content?: AnthropicContentBlock[]
  stop_reason?: string | null
  usage?: {
    input_tokens?: number
    output_tokens?: number
  }
}

export interface AnthropicErrorEnvelope {
  type?: 'error'
  error?: { type?: string | null; message?: string }
}

/** Anthropic SSE 事件（按 `type` 区分） */
export type AnthropicSseEvent =
  | { type: 'message_start'; message?: AnthropicMessage }
  | { type: 'content_block_start'; index?: number; content_block?: AnthropicContentBlock }
  | {
      type: 'content_block_delta'
      index?: number
      delta?: { type?: string; text?: string }
    }
  | { type: 'content_block_stop'; index?: number }
  | {
      type: 'message_delta'
      delta?: { stop_reason?: string | null }
      usage?: { output_tokens?: number }
    }
  | { type: 'message_stop' }
  | { type: 'ping' }
  | { type: 'error'; error?: { type?: string | null; message?: string } }
  | { type: string }

export interface ParseAnthropicSseResult {
  events: AnthropicSseEvent[]
  rest: string
  done: boolean
}

/** 解析 SSE 缓冲：返回完整事件块中的 JSON 事件；`message_stop` 视为结束。 */
export function parseAnthropicSseBuffer(buffer: string): ParseAnthropicSseResult {
  const events: AnthropicSseEvent[] = []
  let rest = buffer
  let done = false
  let sep = rest.indexOf('\n\n')
  while (sep !== -1) {
    const block = rest.slice(0, sep)
    rest = rest.slice(sep + 2)
    let dataPayload = ''
    for (const line of block.split('\n')) {
      const trimmed = line.trim()
      if (trimmed.startsWith('data:')) {
        dataPayload = trimmed.slice(5).trim()
      }
    }
    if (dataPayload.length === 0) {
      sep = rest.indexOf('\n\n')
      continue
    }
    try {
      const evt = JSON.parse(dataPayload) as AnthropicSseEvent
      events.push(evt)
      if (evt.type === 'message_stop') done = true
    } catch {
      // 忽略非 JSON 行（注释 / 心跳）
    }
    sep = rest.indexOf('\n\n')
  }
  return { events, rest, done }
}

/** 从 Anthropic 错误体（HTTP 非 2xx）提取 Playground 错误信息。 */
export function extractAnthropicError(
  json: AnthropicErrorEnvelope | null,
  httpStatus: number,
  fallback: string
): PlaygroundError {
  const err = json?.error
  const trimmed = err?.message?.trim()
  return {
    httpStatus,
    code: err?.type ?? null,
    message: trimmed && trimmed.length > 0 ? trimmed : fallback,
  }
}

/** 从 Anthropic 非流式响应中拼合首段 text 内容（不含 tool_use 等其它 block）。 */
export function pickAnthropicText(message: AnthropicMessage | null): string {
  if (message?.content === undefined) return ''
  const out: string[] = []
  for (const block of message.content) {
    if (block.type === 'text' && typeof block.text === 'string') {
      out.push(block.text)
    }
  }
  return out.join('')
}
