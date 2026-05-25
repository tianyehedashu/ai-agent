import { describe, expect, it } from 'vitest'

import {
  normalizeCredential,
  normalizeCredentialScope,
  type ProviderCredentialWire,
} from './credential-normalize'

function wire(overrides: Partial<ProviderCredentialWire> = {}): ProviderCredentialWire {
  return {
    id: 'c1',
    tenant_id: null,
    scope: 'user',
    scope_id: null,
    provider: 'openai',
    name: 'test',
    api_base: null,
    is_active: true,
    extra: null,
    created_at: '2026-01-01T00:00:00Z',
    api_key_masked: 'sk-…xxxx',
    ...overrides,
  }
}

describe('normalizeCredentialScope', () => {
  it('maps null scope with tenant_id to team', () => {
    expect(normalizeCredentialScope(null, 'team-1')).toBe('team')
  })

  it('passes through system and user', () => {
    expect(normalizeCredentialScope('system', null)).toBe('system')
    expect(normalizeCredentialScope('user', 'team-1')).toBe('user')
  })
})

describe('normalizeCredential', () => {
  it('maps visibility from wire', () => {
    const row = normalizeCredential(wire({ scope: 'system', visibility: 'restricted' }))
    expect(row.visibility).toBe('restricted')
  })
})
