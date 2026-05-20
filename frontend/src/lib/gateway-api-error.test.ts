import { describe, expect, test } from 'vitest'

import { ApiError } from '@/api/errors'

import { messageFromApiErrorBody, parseFastApiDetail } from './fastapi-error-detail'
import { formatGatewayManagementError } from './gateway-api-error'

describe('fastapi-error-detail', () => {
  test('parseFastApiDetail handles nested OpenAI error object', () => {
    expect(
      parseFastApiDetail({
        error: { message: 'rate limited', type: 'rate_limit' },
      })
    ).toBe('rate limited')
  })

  test('messageFromApiErrorBody parses string detail', () => {
    expect(messageFromApiErrorBody({ detail: '虚拟 Key 不存在: x' }, 'fallback')).toBe(
      '虚拟 Key 不存在: x'
    )
  })
})

describe('gateway-api-error', () => {
  test('formatGatewayManagementError maps generic 404 Not Found', () => {
    const err = new ApiError(404, 'Not Found')
    expect(formatGatewayManagementError(err)).toContain('接口不存在')
  })
})
