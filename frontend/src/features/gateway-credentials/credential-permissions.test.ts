import { describe, expect, it } from 'vitest'

import type { CredentialSummary, ProviderCredential } from '@/api/gateway'
import type { GatewayTeam } from '@/api/gateway/teams'

import {
  canBindCredentialForTeamModel,
  canCreateTeamCredential,
  canEditGatewayCredential,
  canLinkToCredentialDetail,
  canManageSystemCredentialVisibility,
  credentialDetailTeamId,
  isWritableTargetTeam,
} from './credential-permissions'

const viewerId = 'user-viewer'
const ownerId = 'user-owner'

function cred(
  scope: ProviderCredential['scope'],
  createdBy: string | null = null
): ProviderCredential {
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
    created_by_user_id: createdBy,
  }
}

const ownedTeamSummary: CredentialSummary = {
  id: 'cred-owned',
  provider: 'openai',
  name: 'Team OpenAI',
  scope: 'team',
  is_active: true,
  is_config_managed: false,
  created_by_user_id: ownerId,
}

const systemSummary: CredentialSummary = {
  id: 'cred-sys',
  provider: 'openai',
  name: 'Platform OpenAI',
  scope: 'system',
  is_active: true,
  is_config_managed: true,
}

describe('canEditGatewayCredential', () => {
  it('allows owner on team cred', () => {
    expect(canEditGatewayCredential(cred('team', ownerId), ownerId, false, false)).toBe(true)
  })

  it('denies non-owner member on team cred', () => {
    expect(canEditGatewayCredential(cred('team', ownerId), viewerId, false, false)).toBe(false)
  })

  it('denies team admin on cred without ownership', () => {
    expect(canEditGatewayCredential(cred('team', null), viewerId, true, false)).toBe(false)
  })

  it('allows system cred for platform admin only', () => {
    expect(canEditGatewayCredential(cred('system'), viewerId, true, true)).toBe(true)
    expect(canEditGatewayCredential(cred('system'), viewerId, true, false)).toBe(false)
  })

  it('denies edit when management_access is metadata even for owner fields', () => {
    expect(
      canEditGatewayCredential(
        { ...cred('team', ownerId), management_access: 'metadata' },
        ownerId,
        true,
        false
      )
    ).toBe(false)
  })
})

describe('canLinkToCredentialDetail', () => {
  it('allows owner on owned team credential', () => {
    expect(canLinkToCredentialDetail(ownedTeamSummary, ownerId, false, false)).toBe(true)
  })

  it('blocks non-owner member on owned team credential', () => {
    expect(canLinkToCredentialDetail(ownedTeamSummary, viewerId, false, false)).toBe(false)
  })

  it('blocks team admin without ownership', () => {
    expect(
      canLinkToCredentialDetail(
        { ...ownedTeamSummary, created_by_user_id: null },
        viewerId,
        true,
        false
      )
    ).toBe(false)
  })

  it('blocks non-platform admin on system credential', () => {
    expect(canLinkToCredentialDetail(systemSummary, viewerId, true, false)).toBe(false)
  })

  it('allows platform admin on system credential', () => {
    expect(canLinkToCredentialDetail(systemSummary, viewerId, true, true)).toBe(true)
  })

  it('blocks detail link when management_access is metadata', () => {
    expect(
      canLinkToCredentialDetail(
        { ...ownedTeamSummary, management_access: 'metadata' },
        ownerId,
        true,
        false
      )
    ).toBe(false)
  })
})

describe('canBindCredentialForTeamModel', () => {
  it('allows owner to bind own credential', () => {
    expect(canBindCredentialForTeamModel(cred('team', ownerId), ownerId, false)).toBe(true)
  })

  it('denies admin binding credential without ownership', () => {
    expect(canBindCredentialForTeamModel(cred('team', null), viewerId, true)).toBe(false)
  })

  it('denies member binding others credential', () => {
    expect(canBindCredentialForTeamModel(cred('team', ownerId), viewerId, false)).toBe(false)
  })
})

describe('canCreateTeamCredential', () => {
  it('allows shared team', () => {
    expect(canCreateTeamCredential({ kind: 'shared' })).toBe(true)
  })

  it('blocks personal team', () => {
    expect(canCreateTeamCredential({ kind: 'personal' })).toBe(false)
  })
})

describe('canManageSystemCredentialVisibility', () => {
  it('allows platform admin only', () => {
    expect(canManageSystemCredentialVisibility(true)).toBe(true)
    expect(canManageSystemCredentialVisibility(false)).toBe(false)
  })
})

describe('credentialDetailTeamId', () => {
  it('uses tenant_id for team credentials', () => {
    expect(credentialDetailTeamId(cred('team'), 'route-team')).toBe('t1')
  })

  it('falls back to route for system credentials', () => {
    expect(credentialDetailTeamId(cred('system'), 'route-team')).toBe('route-team')
  })
})

describe('isWritableTargetTeam', () => {
  const teams: GatewayTeam[] = [
    {
      id: 't1',
      name: 'A',
      slug: 'a',
      kind: 'shared',
      owner_user_id: 'o1',
    },
  ]

  it('matches writable team id', () => {
    expect(isWritableTargetTeam('t1', teams)).toBe(true)
    expect(isWritableTargetTeam('t2', teams)).toBe(false)
  })
})
