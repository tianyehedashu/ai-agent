import { describe, expect, it } from 'vitest'

import type { CredentialSummary, ProviderCredential } from '@/api/gateway'
import type { GatewayTeam } from '@/api/gateway/teams'

import {
  canEditGatewayCredential,
  canLinkToCredentialDetail,
  canManageSystemCredentialVisibility,
  canViewCrossTeamCredentialsOverview,
  credentialDetailTeamId,
  isWritableTargetTeam,
  shouldShowTeamAffiliationColumn,
} from './credential-permissions'

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

const teamSummary: CredentialSummary = {
  id: 'cred-team',
  provider: 'openai',
  name: 'Team OpenAI',
  scope: 'team',
  is_active: true,
  is_config_managed: false,
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
})

describe('canLinkToCredentialDetail', () => {
  it('allows team admin on team credential', () => {
    expect(canLinkToCredentialDetail(teamSummary, true, false)).toBe(true)
  })

  it('blocks member without admin', () => {
    expect(canLinkToCredentialDetail(teamSummary, false, false)).toBe(false)
  })

  it('blocks non-platform admin on system credential', () => {
    expect(canLinkToCredentialDetail(systemSummary, true, false)).toBe(false)
  })

  it('allows platform admin on system credential', () => {
    expect(canLinkToCredentialDetail(systemSummary, true, true)).toBe(true)
  })
})

describe('canViewCrossTeamCredentialsOverview', () => {
  it('requires write and multiple writable teams', () => {
    expect(canViewCrossTeamCredentialsOverview(true, 2)).toBe(true)
    expect(canViewCrossTeamCredentialsOverview(true, 1)).toBe(false)
    expect(canViewCrossTeamCredentialsOverview(false, 3)).toBe(false)
  })
})

describe('canManageSystemCredentialVisibility', () => {
  it('allows platform admin only', () => {
    expect(canManageSystemCredentialVisibility(true)).toBe(true)
    expect(canManageSystemCredentialVisibility(false)).toBe(false)
  })
})

describe('shouldShowTeamAffiliationColumn', () => {
  it('shows in cross-team view always', () => {
    expect(shouldShowTeamAffiliationColumn('cross-team', 1)).toBe(true)
  })

  it('shows in current view only for multi-team admins', () => {
    expect(shouldShowTeamAffiliationColumn('current-team', 2)).toBe(true)
    expect(shouldShowTeamAffiliationColumn('current-team', 1)).toBe(false)
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
