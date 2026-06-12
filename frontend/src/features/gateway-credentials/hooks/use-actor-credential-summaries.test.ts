import { describe, expect, it } from 'vitest'

import type { PlaygroundCredentialSummary } from '@/api/gateway'

import {
  collectQuotaBatchTargetTeamIds,
  filterPlatformQuotaCredentialSummaries,
  filterUpstreamQuotaCredentialSummaries,
  resolveActorCredentialContextTeamId,
} from './use-actor-credential-summaries'

function summary(
  partial: Partial<PlaygroundCredentialSummary> & Pick<PlaygroundCredentialSummary, 'id' | 'name'>
): PlaygroundCredentialSummary {
  return {
    provider: 'openai',
    scope: 'team',
    is_active: true,
    is_config_managed: false,
    context_team_id: 'team-a',
    ...partial,
  }
}

describe('resolveActorCredentialContextTeamId', () => {
  it('falls back to route team when credential has no context', () => {
    const map = new Map<string, string | null>([['c1', null]])
    expect(resolveActorCredentialContextTeamId('c1', map, 'route-team')).toBe('route-team')
  })
})

describe('filterUpstreamQuotaCredentialSummaries', () => {
  it('excludes personal BYOK and non-admin team creds', () => {
    const adminTeams = new Set(['team-a'])
    const creds = [
      summary({ id: 'personal', name: 'p', scope: 'user', context_team_id: 'team-a' }),
      summary({ id: 'team-a-cred', name: 'a', context_team_id: 'team-a' }),
      summary({ id: 'team-b-cred', name: 'b', context_team_id: 'team-b' }),
    ]
    const filtered = filterUpstreamQuotaCredentialSummaries(creds, adminTeams, false)
    expect(filtered.map((c) => c.id)).toEqual(['team-a-cred'])
  })
})

describe('filterPlatformQuotaCredentialSummaries', () => {
  it('only includes creds for the route team', () => {
    const creds = [
      summary({ id: 'a', name: 'a', context_team_id: 'team-a' }),
      summary({ id: 'b', name: 'b', context_team_id: 'team-b' }),
    ]
    expect(filterPlatformQuotaCredentialSummaries(creds, 'team-a', false).map((c) => c.id)).toEqual(
      ['a']
    )
  })
})

describe('collectQuotaBatchTargetTeamIds', () => {
  it('includes upstream credential context teams', () => {
    const map = new Map<string, string | null>([['c-b', 'team-b']])
    const teamIds = collectQuotaBatchTargetTeamIds(
      'team-a',
      [{ layer: 'platform' }, { layer: 'upstream', credential_id: 'c-b' }],
      map
    )
    expect(teamIds.sort()).toEqual(['team-a', 'team-b'])
  })
})
