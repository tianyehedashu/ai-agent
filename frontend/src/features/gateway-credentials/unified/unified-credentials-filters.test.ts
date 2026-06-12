import { describe, expect, it } from 'vitest'

import type { ProviderCredential } from '@/api/gateway'

import {
  filterUnifiedCredentialEntries,
  matchesCredentialSearch,
  paginateUnifiedCredentialEntries,
} from './unified-credentials-filters'

function personalCred(name: string): ProviderCredential {
  return {
    id: `p-${name}`,
    tenant_id: null,
    scope: 'user',
    scope_id: null,
    provider: 'openai',
    name,
    api_base: null,
    extra: null,
    is_active: true,
    api_key_masked: 'sk-***',
    created_at: '2026-01-01T00:00:00Z',
  }
}

function teamCred(name: string, tenantId: string): ProviderCredential {
  return {
    ...personalCred(name),
    id: `t-${name}`,
    scope: 'team',
    tenant_id: tenantId,
  }
}

describe('unified-credentials-filters', () => {
  const teamNameById = new Map([['team-1', '研发']])

  it('matchesCredentialSearch by affiliation', () => {
    const entry = { kind: 'full' as const, credential: teamCred('k1', 'team-1') }
    expect(matchesCredentialSearch(entry, '研发', teamNameById)).toBe(true)
    expect(matchesCredentialSearch(entry, '不存在', teamNameById)).toBe(false)
  })

  it('filterUnifiedCredentialEntries by scope', () => {
    const entries = [
      { kind: 'full' as const, credential: personalCred('my') },
      { kind: 'full' as const, credential: teamCred('team', 'team-1') },
    ]
    const personalOnly = filterUnifiedCredentialEntries(entries, {
      search: '',
      scopeFilter: 'user',
      teamNameById,
    })
    expect(personalOnly).toHaveLength(1)
    expect(personalOnly[0]?.kind === 'full' && personalOnly[0].credential.name).toBe('my')
  })

  it('paginateUnifiedCredentialEntries', () => {
    const entries = Array.from({ length: 25 }, (_, i) => ({
      kind: 'full' as const,
      credential: personalCred(String(i)),
    }))
    const page1 = paginateUnifiedCredentialEntries(entries, 1, 20)
    expect(page1.items).toHaveLength(20)
    expect(page1.total).toBe(25)
    expect(page1.has_next).toBe(true)
    expect(page1.has_prev).toBe(false)

    const page2 = paginateUnifiedCredentialEntries(entries, 2, 20)
    expect(page2.items).toHaveLength(5)
    expect(page2.has_next).toBe(false)
    expect(page2.has_prev).toBe(true)
  })
})
