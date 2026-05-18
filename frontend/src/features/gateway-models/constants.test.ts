/**
 * @see constants.ts
 */

import { describe, expect, it } from 'vitest'

import { CAPABILITY_LABELS, capabilityLabel } from './constants'

describe('capabilityLabel', () => {
  it('returns Chinese label for known capability', () => {
    expect(capabilityLabel('chat')).toBe(CAPABILITY_LABELS.chat)
    expect(capabilityLabel('embedding')).toBe('向量 Embedding')
  })

  it('falls back to raw value for unknown capability', () => {
    expect(capabilityLabel('custom_cap')).toBe('custom_cap')
  })
})
