/**
 * @see provider-credential-mask-display.ts
 */

import { describe, expect, it } from 'vitest'

import { displayListApiKeyMasked } from './provider-credential-mask-display'

describe('displayListApiKeyMasked', () => {
  it('hides when no session', () => {
    expect(displayListApiKeyMasked(true, false, 'sk-a…bcde')).toBe('········（已隐藏）')
  })

  it('hides when session but switch off', () => {
    expect(displayListApiKeyMasked(false, true, 'sk-a…bcde')).toBe('········（已隐藏）')
  })

  it('shows masked when session and switch on', () => {
    expect(displayListApiKeyMasked(true, true, 'sk-a…bcde')).toBe('sk-a…bcde')
  })
})
