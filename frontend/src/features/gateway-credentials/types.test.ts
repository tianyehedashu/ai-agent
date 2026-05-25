/**
 * @see types.ts
 */

import { describe, expect, it } from 'vitest'

import { isPersonalUpstreamScope, managedCredentialUpstreamScope } from './types'

describe('isPersonalUpstreamScope', () => {
  it('returns true only for user scope', () => {
    expect(isPersonalUpstreamScope('user')).toBe(true)
    expect(isPersonalUpstreamScope('team')).toBe(false)
    expect(isPersonalUpstreamScope('system')).toBe(false)
  })
})

describe('managedCredentialUpstreamScope', () => {
  it('maps system scope to system upstream scope', () => {
    expect(managedCredentialUpstreamScope('system')).toBe('system')
  })

  it('maps team and user credential scopes to team upstream API', () => {
    expect(managedCredentialUpstreamScope('team')).toBe('team')
    expect(managedCredentialUpstreamScope('user')).toBe('team')
    expect(managedCredentialUpstreamScope(null)).toBe('team')
  })
})

describe('upstream probe routing', () => {
  it('system credentials use managed team API not personal', () => {
    expect(isPersonalUpstreamScope(managedCredentialUpstreamScope('system'))).toBe(false)
  })
})
