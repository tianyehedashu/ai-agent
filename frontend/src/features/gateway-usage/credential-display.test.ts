import { describe, expect, it } from 'vitest'

import {
  credentialDisplayText,
  credentialDisplayTitle,
  marginGroupRowTitle,
} from './credential-display'

describe('credentialDisplay', () => {
  it('prefers snapshot name', () => {
    expect(
      credentialDisplayText({
        credential_id: '11111111-1111-1111-1111-111111111111',
        credential_name_snapshot: '生产',
      })
    ).toBe('生产')
  })

  it('falls back to truncated id when no snapshot name', () => {
    expect(
      credentialDisplayText({
        credential_id: '11111111-1111-1111-1111-111111111111',
      })
    ).toBe('11111111…')
    expect(credentialDisplayText({})).toBe('—')
  })

  it('credentialDisplayTitle composes name and full id when both present', () => {
    expect(
      credentialDisplayTitle({
        credential_id: '11111111-1111-1111-1111-111111111111',
        credential_name_snapshot: '生产',
      })
    ).toBe('生产 · 11111111-1111-1111-1111-111111111111')
    expect(
      credentialDisplayTitle({
        credential_id: '11111111-1111-1111-1111-111111111111',
      })
    ).toBe('11111111-1111-1111-1111-111111111111')
    expect(credentialDisplayTitle({})).toBeUndefined()
  })

  it('marginGroupRowTitle combines label and key', () => {
    expect(marginGroupRowTitle('生产', 'uuid-full')).toBe('生产 · uuid-full')
    expect(marginGroupRowTitle('uuid-full', 'uuid-full')).toBe('uuid-full')
    expect(marginGroupRowTitle('生产', null)).toBeUndefined()
  })
})
