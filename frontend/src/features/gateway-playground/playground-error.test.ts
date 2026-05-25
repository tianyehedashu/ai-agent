import { describe, expect, it } from 'vitest'

import { extractPlaygroundHttpError, withReferenceImagePayloadHint } from './playground-error'

describe('extractPlaygroundHttpError', () => {
  it('解析 FastAPI OpenAI detail.error', () => {
    const err = extractPlaygroundHttpError(
      {
        detail: {
          error: {
            type: 'model_not_allowed',
            message: '模型不在虚拟 Key 白名单内',
          },
        },
      },
      403,
      'fallback',
      'openai'
    )
    expect(err.message).toBe('模型不在虚拟 Key 白名单内')
    expect(err.code).toBe('model_not_allowed')
    expect(err.httpStatus).toBe(403)
  })

  it('解析 FastAPI 字符串 detail', () => {
    const err = extractPlaygroundHttpError(
      { detail: 'Missing credentials' },
      401,
      'fallback',
      'openai'
    )
    expect(err.message).toBe('Missing credentials')
  })

  it('解析 FastAPI Anthropic detail 嵌套', () => {
    const err = extractPlaygroundHttpError(
      {
        detail: {
          type: 'error',
          error: { type: 'rate_limit_error', message: '套餐额度已用尽' },
        },
      },
      429,
      'fallback',
      'anthropic'
    )
    expect(err.message).toBe('套餐额度已用尽')
    expect(err.code).toBe('rate_limit_error')
  })

  it('仍兼容顶层 OpenAI error', () => {
    const err = extractPlaygroundHttpError(
      { error: { message: 'invalid model', code: 'model_not_found' } },
      404,
      'fallback',
      'openai'
    )
    expect(err.message).toBe('invalid model')
    expect(err.code).toBe('model_not_found')
  })
})

describe('withReferenceImagePayloadHint', () => {
  it('413 with data URL adds upload hint', () => {
    const err = withReferenceImagePayloadHint(
      { httpStatus: 413, message: 'Payload Too Large' },
      'data:image/png;base64,abc'
    )
    expect(err?.hint).toContain('上传')
  })

  it('non-payload error unchanged', () => {
    const base = { httpStatus: 401, message: 'Unauthorized' }
    expect(withReferenceImagePayloadHint(base, 'data:image/png;base64,x')).toEqual(base)
  })

  it('413 without reference image unchanged', () => {
    const base = { httpStatus: 413, message: 'Payload Too Large' }
    expect(withReferenceImagePayloadHint(base)).toEqual(base)
  })
})
