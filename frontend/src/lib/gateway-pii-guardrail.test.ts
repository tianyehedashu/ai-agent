import { describe, expect, it } from 'vitest'

import { guardrailStatusLabel } from './gateway-pii-guardrail'

describe('guardrailStatusLabel', () => {
  it('returns 未开放 when global switch is off', () => {
    expect(guardrailStatusLabel(true, false)).toBe('未开放')
    expect(guardrailStatusLabel(false, false)).toBe('未开放')
  })

  it('reflects per-key switch when global switch is on', () => {
    expect(guardrailStatusLabel(true, true)).toBe('已启用')
    expect(guardrailStatusLabel(false, true)).toBe('关闭')
  })
})
