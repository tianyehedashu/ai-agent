import { describe, expect, test } from 'vitest'

import { ApiError } from '@/api/client'

import { formatGatewayManagementError, messageFromApiErrorBody } from './gateway-api-error'

describe('gateway-api-error', () => {
  test('messageFromApiErrorBody parses string detail', () => {
    expect(messageFromApiErrorBody({ detail: '虚拟 Key 不存在: x' }, 'fallback')).toBe(
      '虚拟 Key 不存在: x'
    )
  })

  test('formatGatewayManagementError maps generic 404 Not Found', () => {
    const err = new ApiError(404, 'Not Found')
    expect(formatGatewayManagementError(err)).toContain('接口不存在')
  })
})
