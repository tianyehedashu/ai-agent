import { describe, expect, it } from 'vitest'

import type { VirtualKeyTeamGrant } from '@/api/gateway/grants'

import {
  buildMultiGrantTeamModelGroups,
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

describe('buildMultiGrantTeamModelGroups', () => {
  const teamRow: ModelCandidate = {
    name: 'team-m',
    scope: 'team',
    status: 'success',
    capability: 'chat',
    provider: 'openai',
  }

  const grants: VirtualKeyTeamGrant[] = [
    {
      id: 'g1',
      vkey_id: 'k1',
      tenant_id: 'team-a',
      is_self: true,
      created_at: '',
      revoked_at: null,
      granted_team_name: 'Alpha Team',
      granted_team_slug: 'alpha',
    },
    {
      id: 'g2',
      vkey_id: 'k1',
      tenant_id: 'team-b',
      is_self: false,
      created_at: '',
      revoked_at: null,
      granted_team_name: 'Beta Team',
      granted_team_slug: 'beta',
    },
  ]

  it('groups proxy models by team slug with primary first', () => {
    const models: ModelCandidate[] = [
      { ...teamRow, name: 'beta/gpt-4o', teamSlug: 'beta' },
      { ...teamRow, name: 'gpt-4o', teamSlug: null },
      { ...teamRow, name: 'gamma/claude', teamSlug: 'gamma' },
    ]
    const groups = buildMultiGrantTeamModelGroups(models, [
      ...grants,
      {
        id: 'g3',
        vkey_id: 'k1',
        tenant_id: 'team-c',
        is_self: false,
        created_at: '',
        revoked_at: null,
        granted_team_name: 'Gamma Team',
        granted_team_slug: 'gamma',
      },
    ])
    expect(groups?.map((g) => g.label)).toEqual([
      'Alpha Team · 个人',
      'Beta Team (beta)',
      'Gamma Team (gamma)',
    ])
    expect(groups?.[0]?.models.map((m) => m.name)).toEqual(['gpt-4o'])
    expect(groups?.[1]?.models.map((m) => m.name)).toEqual(['beta/gpt-4o'])
    expect(groups?.[2]?.models.map((m) => m.name)).toEqual(['gamma/claude'])
  })

  it('returns undefined for single-team lists', () => {
    expect(buildMultiGrantTeamModelGroups([{ ...teamRow, teamSlug: null }], grants)).toBeUndefined()
  })

  it('infers team bucket from model name prefix when teamSlug missing', () => {
    const groups = buildMultiGrantTeamModelGroups(
      [
        { ...teamRow, name: 'gpt-4o', teamSlug: null },
        { ...teamRow, name: 'team-982b6a39/composer-2-5-chat' },
      ],
      grants
    )
    expect(groups).toHaveLength(2)
    expect(groups?.[0]?.label).toBe('Alpha Team · 个人')
    expect(groups?.[1]?.label).toBe('team-982b6a39')
    expect(groups?.[1]?.models.map((m) => m.name)).toEqual(['team-982b6a39/composer-2-5-chat'])
  })
})
