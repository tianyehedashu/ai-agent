/**
 * OpenAI 兼容 SSE / 错误解析单测
 */

import { describe, expect, it } from 'vitest'

import {
  extractOpenAiCompatError,
  extractResponseCostUsd,
  parseOpenAiSseBuffer,
} from './openai-sse'

describe('parseOpenAiSseBuffer', () => {
  it('解析单个 data 块并保留未完成缓冲', () => {
    const input = 'data: {"choices":[{"delta":{"content":"Hi"}}]}\n\ndata: partial'
    const { chunks, rest, done } = parseOpenAiSseBuffer(input)
    expect(chunks).toHaveLength(1)
    expect(chunks[0]?.choices?.[0]?.delta?.content).toBe('Hi')
    expect(rest).toBe('data: partial')
    expect(done).toBe(false)
  })

  it('识别 [DONE] 并继续解析后续块', () => {
    const input =
      'data: {"choices":[{"delta":{"content":"A"}}]}\n\n' +
      'data: [DONE]\n\n' +
      'data: {"choices":[{"delta":{"content":"B"}}]}\n\n'
    const { chunks, done } = parseOpenAiSseBuffer(input)
    expect(chunks).toHaveLength(2)
    expect(chunks[0]?.choices?.[0]?.delta?.content).toBe('A')
    expect(chunks[1]?.choices?.[0]?.delta?.content).toBe('B')
    expect(done).toBe(true)
  })

  it('忽略非 JSON data 行', () => {
    const input = 'data: :heartbeat\n\ndata: {"choices":[]}\n\n'
    const { chunks } = parseOpenAiSseBuffer(input)
    expect(chunks).toHaveLength(1)
  })
})

describe('extractResponseCostUsd', () => {
  it('读取 response_cost 字段', () => {
    expect(extractResponseCostUsd({ response_cost: 0.0012 })).toBe(0.0012)
    expect(extractResponseCostUsd({ response_cost: -1 })).toBeUndefined()
    expect(extractResponseCostUsd(null)).toBeUndefined()
  })
})

describe('extractOpenAiCompatError', () => {
  it('优先使用 error.message', () => {
    const err = extractOpenAiCompatError(
      { error: { message: '  invalid model  ', code: 'model_not_found' } },
      404,
      'fallback'
    )
    expect(err.message).toBe('invalid model')
    expect(err.code).toBe('model_not_found')
    expect(err.httpStatus).toBe(404)
  })

  it('无 message 时回退 fallback', () => {
    const err = extractOpenAiCompatError(null, 500, 'HTTP 500 Internal Server Error')
    expect(err.message).toBe('HTTP 500 Internal Server Error')
    expect(err.code).toBeNull()
  })

  it('code 缺失时使用 type', () => {
    const err = extractOpenAiCompatError(
      { error: { message: 'rate limited', type: 'rate_limit_exceeded' } },
      429,
      'fallback'
    )
    expect(err.code).toBe('rate_limit_exceeded')
  })
})
