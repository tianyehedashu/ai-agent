/**
 * Anthropic 兼容 SSE / 错误 / 文本拼合解析单测
 */

import { describe, expect, it } from 'vitest'

import {
  extractAnthropicDeltaText,
  extractAnthropicError,
  parseAnthropicSseBuffer,
  pickAnthropicText,
  pickAnthropicThinking,
} from './anthropic-sse'

describe('parseAnthropicSseBuffer', () => {
  it('解析多个事件并识别 message_stop 作为结束信号', () => {
    const input =
      'event: message_start\n' +
      'data: {"type":"message_start","message":{"id":"msg_1","model":"m","usage":{"input_tokens":3}}}\n\n' +
      'event: content_block_delta\n' +
      'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"Hi"}}\n\n' +
      'event: content_block_delta\n' +
      'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"!"}}\n\n' +
      'event: message_delta\n' +
      'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":2}}\n\n' +
      'event: message_stop\n' +
      'data: {"type":"message_stop"}\n\n'

    const { events, rest, done } = parseAnthropicSseBuffer(input)
    expect(events).toHaveLength(5)
    expect(events[0]?.type).toBe('message_start')
    expect(events[1]?.type).toBe('content_block_delta')
    expect(rest).toBe('')
    expect(done).toBe(true)
  })

  it('保留未完成的事件块在 rest 中', () => {
    const input =
      'event: content_block_delta\n' +
      'data: {"type":"content_block_delta","index":0,"delta":{"type":"text_delta","text":"part"}}\n\n' +
      'event: content_block_delta\n' +
      'data: {"type":"content_block_delta"' // 半截
    const { events, rest, done } = parseAnthropicSseBuffer(input)
    expect(events).toHaveLength(1)
    expect(rest).toContain('"content_block_delta"')
    expect(done).toBe(false)
  })

  it('忽略非 JSON 的 data 行', () => {
    const input =
      'event: ping\ndata: ping\n\nevent: message_stop\ndata: {"type":"message_stop"}\n\n'
    const { events, done } = parseAnthropicSseBuffer(input)
    expect(events).toHaveLength(1)
    expect(events[0]?.type).toBe('message_stop')
    expect(done).toBe(true)
  })
})

describe('extractAnthropicDeltaText', () => {
  it('解析 text_delta 与 thinking_delta', () => {
    expect(
      extractAnthropicDeltaText({
        type: 'content_block_delta',
        delta: { type: 'text_delta', text: 'Hi' },
      })
    ).toEqual({ text: 'Hi', thinking: '' })
    expect(
      extractAnthropicDeltaText({
        type: 'content_block_delta',
        delta: { type: 'thinking_delta', thinking: 'plan...' },
      })
    ).toEqual({ text: '', thinking: 'plan...' })
  })
})

describe('pickAnthropicText', () => {
  it('拼合所有 type=text 的 content block', () => {
    expect(
      pickAnthropicText({
        content: [
          { type: 'text', text: 'Hello, ' },
          { type: 'tool_use' },
          { type: 'text', text: 'world!' },
        ],
      })
    ).toBe('Hello, world!')
  })

  it('null / 空 content 返回空串', () => {
    expect(pickAnthropicText(null)).toBe('')
    expect(pickAnthropicText({})).toBe('')
    expect(pickAnthropicText({ content: [] })).toBe('')
  })
})

describe('pickAnthropicThinking', () => {
  it('拼合所有 type=thinking 的 content block', () => {
    expect(
      pickAnthropicThinking({
        content: [
          { type: 'thinking', thinking: 'step 1' },
          { type: 'text', text: 'answer' },
          { type: 'thinking', thinking: ' step 2' },
        ],
      })
    ).toBe('step 1 step 2')
  })

  it('null / 空 content 返回空串', () => {
    expect(pickAnthropicThinking(null)).toBe('')
    expect(pickAnthropicThinking({ content: [] })).toBe('')
  })
})

describe('extractAnthropicError', () => {
  it('优先使用 error.message', () => {
    const err = extractAnthropicError(
      { type: 'error', error: { type: 'invalid_request_error', message: '  bad model  ' } },
      400,
      'fallback'
    )
    expect(err.message).toBe('bad model')
    expect(err.code).toBe('invalid_request_error')
    expect(err.httpStatus).toBe(400)
  })

  it('无 message 时回退 fallback', () => {
    const err = extractAnthropicError(null, 500, 'HTTP 500 boom')
    expect(err.message).toBe('HTTP 500 boom')
    expect(err.code).toBeNull()
  })
})
