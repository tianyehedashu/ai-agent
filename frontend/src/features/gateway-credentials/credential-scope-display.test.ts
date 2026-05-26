import { describe, expect, it } from 'vitest'

import {
  credentialScopeLabel,
  credentialTeamLabel,
  systemVisibilityLabel,
} from './credential-scope-labels'

describe('credentialScopeLabel', () => {
  it('maps known scopes', () => {
    expect(credentialScopeLabel('team')).toBe('团队')
    expect(credentialScopeLabel('system')).toBe('系统')
    expect(credentialScopeLabel('user')).toBe('个人')
  })

  it('falls back for unknown', () => {
    expect(credentialScopeLabel(null)).toBe('—')
  })
})

describe('credentialTeamLabel', () => {
  it('resolves team name from map', () => {
    const map = new Map([['t1', '研发团队']])
    expect(credentialTeamLabel('t1', map)).toBe('研发团队')
  })

  it('returns dash when tenant missing', () => {
    expect(credentialTeamLabel(null, new Map())).toBe('—')
  })
})

describe('systemVisibilityLabel', () => {
  it('maps visibility values', () => {
    expect(systemVisibilityLabel('public')).toBe('公开')
    expect(systemVisibilityLabel('restricted')).toBe('受限')
    expect(systemVisibilityLabel(null)).toBe('公开')
  })
})
