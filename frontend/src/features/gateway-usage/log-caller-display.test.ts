import { describe, expect, it } from 'vitest'

import {
  logCallerDisplayText,
  logCallerDisplayTitle,
} from '@/features/gateway-usage/log-caller-display'

describe('logCallerDisplayText', () => {
  it('prefers email snapshot', () => {
    expect(
      logCallerDisplayText({
        user_email_snapshot: 'a@b.com',
        user_id: 'uid-1',
      })
    ).toBe('a@b.com')
  })

  it('falls back to user_id', () => {
    expect(
      logCallerDisplayText({
        user_email_snapshot: null,
        user_id: 'uid-1',
      })
    ).toBe('uid-1')
  })

  it('returns em dash when empty', () => {
    expect(
      logCallerDisplayText({
        user_email_snapshot: null,
        user_id: null,
      })
    ).toBe('—')
  })
})

describe('logCallerDisplayTitle', () => {
  it('combines email and user_id', () => {
    expect(
      logCallerDisplayTitle({
        user_email_snapshot: 'a@b.com',
        user_id: 'uid-1',
      })
    ).toBe('a@b.com · uid-1')
  })

  it('returns single field when only one present', () => {
    expect(
      logCallerDisplayTitle({
        user_email_snapshot: 'a@b.com',
        user_id: null,
      })
    ).toBe('a@b.com')
  })
})
