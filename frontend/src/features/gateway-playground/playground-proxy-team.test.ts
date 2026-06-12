import { describe, expect, it } from 'vitest'

import {
  filterPlaygroundCandidatesForVirtualKey,
  filterPlaygroundNamesForVirtualKey,
  resolvePlaygroundProxyTeamId,
  splitPlaygroundModelCandidatesForDisplay,
} from './playground-proxy-team'

import type { PlaygroundCredentialOption } from './playground-credential-options'
import type { ModelCandidate } from './playground-mode-filter'

const teamCred = new Map<string, PlaygroundCredentialOption>([
  [
    'cred-1',
    {
      id: 'cred-1',
      provider: 'openai',
      name: 'Team OpenAI',
      scope: 'team',
      is_active: true,
      is_config_managed: false,
      context_team_id: 'team-a',
    },
  ],
])

describe('resolvePlaygroundProxyTeamId', () => {
  it('uses selected key team when present', () => {
    expect(
      resolvePlaygroundProxyTeamId({ team_id: 'team-key' }, '', teamCred, 'team-workspace')
    ).toBe('team-key')
  })

  it('falls back to credential context team', () => {
    expect(resolvePlaygroundProxyTeamId(null, 'cred-1', teamCred, 'team-workspace')).toBe('team-a')
  })
})

describe('filterPlaygroundCandidatesForVirtualKey', () => {
  const candidates: ModelCandidate[] = [
    {
      name: 'a',
      scope: 'team',
      status: 'success',
      capability: 'chat',
      provider: 'openai',
    },
    {
      name: 'b',
      scope: 'team',
      status: 'success',
      capability: 'chat',
      provider: 'openai',
    },
  ]

  it('returns all when allowed_models empty', () => {
    expect(filterPlaygroundCandidatesForVirtualKey(candidates, [])).toHaveLength(2)
  })

  it('filters by whitelist', () => {
    expect(filterPlaygroundCandidatesForVirtualKey(candidates, ['b']).map((m) => m.name)).toEqual([
      'b',
    ])
  })

  it('filters routes by virtual_model name in whitelist', () => {
    const routes = [{ name: 'smart-route' }, { name: 'other-route' }]
    expect(filterPlaygroundNamesForVirtualKey(routes, ['smart-route']).map((r) => r.name)).toEqual([
      'smart-route',
    ])
  })
})

describe('splitPlaygroundModelCandidatesForDisplay', () => {
  const teamRow: ModelCandidate = {
    name: 'team-m',
    scope: 'team',
    status: 'success',
    capability: 'chat',
    provider: 'openai',
  }
  const personalRow: ModelCandidate = {
    name: 'byok-m',
    scope: 'personal',
    status: 'success',
    capability: 'chat',
    provider: 'openai',
  }

  it('merges registry rows into personal group for personal workspace', () => {
    const { teamCandidates, personalCandidates } = splitPlaygroundModelCandidatesForDisplay(
      [teamRow, personalRow],
      true
    )
    expect(teamCandidates).toHaveLength(0)
    expect(personalCandidates.map((m) => m.name)).toEqual(['team-m', 'byok-m'])
  })

  it('hides personal models for shared team keys', () => {
    const { teamCandidates, personalCandidates } = splitPlaygroundModelCandidatesForDisplay(
      [teamRow, personalRow],
      false
    )
    expect(teamCandidates.map((m) => m.name)).toEqual(['team-m'])
    expect(personalCandidates).toHaveLength(0)
  })
})
