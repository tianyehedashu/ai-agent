import { describe, expect, it } from 'vitest'

import { formatMoney } from '@/lib/money'

describe('formatMoney', () => {
  it('formats CNY by default', () => {
    expect(formatMoney(1.23, { currency: 'CNY' })).toContain('¥')
  })

  it('formats USD', () => {
    expect(formatMoney(0.0012, { currency: 'USD', precision: 4 })).toContain('$')
  })
})
