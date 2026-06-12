import { describe, expect, it } from 'vitest'

import { formatQuotaTokens, tokensToWanInput, wanInputToTokenString } from './quota-token-display'

describe('quota-token-display', () => {
  it('converts between tokens and 万 for form I/O', () => {
    expect(tokensToWanInput('500000')).toBe('50')
    expect(wanInputToTokenString('50')).toBe('500000')
    expect(wanInputToTokenString('1.5')).toBe('15000')
  })

  it('formats token amounts for display', () => {
    expect(formatQuotaTokens(1_000_000)).toBe('100 万')
    expect(formatQuotaTokens(null)).toBe('∞')
  })
})
