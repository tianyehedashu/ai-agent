import { describe, expect, it } from 'vitest'

import type { ProviderCredential } from '@/api/gateway'

import { canEditGatewayCredential } from './credential-edit-policy'

function cred(scope: ProviderCredential['scope']): ProviderCredential {
  return {
    id: 'c1',
    tenant_id: scope === 'team' ? 't1' : null,
    scope,
    scope_id: null,
    provider: 'openai',
    name: 'test',
    api_base: null,
    is_active: true,
    extra: null,
    created_at: '2026-01-01T00:00:00Z',
    api_key_masked: 'sk-…xxxx',
  }
}

describe('canEditGatewayCredential', () => {
  it('allows team cred when canWrite', () => {
    expect(canEditGatewayCredential(cred('team'), true, false)).toBe(true)
  })

  it('denies team cred without write', () => {
    expect(canEditGatewayCredential(cred('team'), false, false)).toBe(false)
  })

  it('allows system cred for platform admin only', () => {
    expect(canEditGatewayCredential(cred('system'), true, true)).toBe(true)
    expect(canEditGatewayCredential(cred('system'), true, false)).toBe(false)
  })

  it('denies user scope on managed policy', () => {
    expect(canEditGatewayCredential(cred('user'), true, true)).toBe(false)
  })
})
