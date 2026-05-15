/**
 * @see mask-display.ts
 */

import { describe, expect, it } from 'vitest'

import { displayListApiKeyMasked } from './mask-display'

describe('displayListApiKeyMasked', () => {
  it('hides when not authenticated', () => {
    expect(displayListApiKeyMasked(true, false, 'sk-***abc')).toBe('········（已隐藏）')
  })

  it('shows masked server value when toggled on and authenticated', () => {
    expect(displayListApiKeyMasked(true, true, 'sk-***abc')).toBe('sk-***abc')
  })

  it('hides fingerprint when toggled off but authenticated', () => {
    expect(displayListApiKeyMasked(false, true, 'sk-***abc')).toBe('········（已隐藏）')
  })
})
