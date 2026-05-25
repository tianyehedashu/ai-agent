import { describe, expect, it } from 'vitest'

import { parseApiErrorBody, parseFastApiDetail } from './fastapi-error-detail'

describe('parseApiErrorBody', () => {
  it('parses RFC 7807 problem details', () => {
    const parsed = parseApiErrorBody(
      {
        type: 'https://ai-agent.local/errors/not-found',
        title: 'Resource not found',
        status: 404,
        detail: 'Session not found',
        code: 'NOT_FOUND',
        extra: { resource: 'Session' },
      },
      'fallback'
    )
    expect(parsed.message).toBe('Session not found')
    expect(parsed.code).toBe('NOT_FOUND')
    expect(parsed.title).toBe('Resource not found')
    expect(parsed.extra).toEqual({ resource: 'Session' })
  })

  it('parses legacy detail string', () => {
    const parsed = parseApiErrorBody({ detail: 'bad request' }, 'fallback')
    expect(parsed.message).toBe('bad request')
  })

  it('parses errors array', () => {
    const parsed = parseApiErrorBody(
      {
        detail: 'Validation failed',
        code: 'VALIDATION_ERROR',
        errors: [{ loc: ['body', 'name'], msg: 'Field required', type: 'missing' }],
      },
      'fallback'
    )
    expect(parsed.errors).toHaveLength(1)
    expect(parsed.errors?.[0].msg).toBe('Field required')
  })
})

describe('parseFastApiDetail', () => {
  it('joins validation array messages', () => {
    expect(parseFastApiDetail([{ msg: 'a' }, { msg: 'b' }])).toBe('a；b')
  })
})
