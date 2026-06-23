import { describe, expect, it } from 'vitest'

import { gatewayRequestStatusLabel, usageStatsStatusRowLabel } from './gateway-request-status'

describe('gatewayRequestStatusLabel', () => {
  it('maps known statuses to Chinese labels', () => {
    expect(gatewayRequestStatusLabel('success')).toBe('成功')
    expect(gatewayRequestStatusLabel('failed')).toBe('失败')
    expect(gatewayRequestStatusLabel('rate_limited')).toBe('限流')
    expect(gatewayRequestStatusLabel('budget_exceeded')).toBe('配额超限')
    expect(gatewayRequestStatusLabel('guardrail_blocked')).toBe('安全拦截')
  })

  it('passes through unknown statuses', () => {
    expect(gatewayRequestStatusLabel('custom')).toBe('custom')
  })
})

describe('usageStatsStatusRowLabel', () => {
  it('prefers group_key for status rows', () => {
    expect(usageStatsStatusRowLabel('budget_exceeded', 'failed')).toBe('配额超限')
  })
})
