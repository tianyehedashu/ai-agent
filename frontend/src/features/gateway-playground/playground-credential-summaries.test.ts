import { describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/api/errors'
import type {
  CredentialSummary,
  PlaygroundCredentialSummary,
  ProviderCredential,
} from '@/api/gateway'

import {
  fetchPlaygroundCredentialSummaries,
  listPlaygroundCredentialSummariesFallback,
  personalCredentialToPlaygroundSummary,
  resolvePlaygroundVirtualKeyTeamIds,
} from './playground-credential-summaries'

const listPlaygroundMock = vi.fn<[], Promise<PlaygroundCredentialSummary[]>>()
const listMyCredentialsMock = vi.fn<[], Promise<ProviderCredential[]>>()
const listCredentialSummariesMock = vi.fn<[string], Promise<CredentialSummary[]>>()

vi.mock('@/api/gateway', () => ({
  gatewayApi: {
    listPlaygroundCredentialSummaries: () => listPlaygroundMock(),
    listMyCredentials: () => listMyCredentialsMock(),
    listCredentialSummaries: (teamId: string) => listCredentialSummariesMock(teamId),
  },
}))

const personalTeam = { id: 'team-p', name: 'Personal', slug: 'p', kind: 'personal' as const }
const sharedTeam = { id: 'team-s', name: '研发', slug: 'dev', kind: 'shared' as const }

const teamSummary: CredentialSummary = {
  id: 'cred-team',
  provider: 'openai',
  name: 'Team OpenAI',
  scope: 'team',
  is_active: true,
  is_config_managed: false,
}

describe('fetchPlaygroundCredentialSummaries', () => {
  it('uses aggregate API when available', async () => {
    listPlaygroundMock.mockResolvedValue([{ ...teamSummary, context_team_id: 'team-s' }])
    const rows = await fetchPlaygroundCredentialSummaries([personalTeam, sharedTeam])
    expect(rows).toHaveLength(1)
    expect(listCredentialSummariesMock).not.toHaveBeenCalled()
  })

  it('falls back to per-team summaries on 404', async () => {
    listPlaygroundMock.mockRejectedValue(new ApiError(404, 'Not Found'))
    listMyCredentialsMock.mockResolvedValue([])
    listCredentialSummariesMock.mockImplementation((teamId: string) =>
      Promise.resolve(teamId === 'team-s' ? [teamSummary] : [])
    )
    const rows = await fetchPlaygroundCredentialSummaries([personalTeam, sharedTeam])
    expect(rows.map((r) => r.id)).toEqual(['cred-team'])
    expect(rows[0]?.context_team_id).toBe('team-s')
  })
})

describe('resolvePlaygroundVirtualKeyTeamIds', () => {
  const byId = new Map([
    ['cred-team', { ...teamSummary, context_team_id: 'team-s' }],
    [
      'cred-user',
      personalCredentialToPlaygroundSummary(
        {
          id: 'cred-user',
          tenant_id: null,
          scope: 'user',
          scope_id: 'u1',
          provider: 'openai',
          name: 'My',
          api_base: null,
          is_active: true,
          extra: null,
          created_at: '',
          api_key_masked: '***',
        } as ProviderCredential,
        'team-p'
      ),
    ],
  ])

  it('aggregates all membership teams when no credential filter', () => {
    expect(resolvePlaygroundVirtualKeyTeamIds('', byId, 'team-p', ['team-p', 'team-s'])).toEqual([
      'team-p',
      'team-s',
    ])
  })

  it('uses credential context team for team/system credentials', () => {
    expect(
      resolvePlaygroundVirtualKeyTeamIds('cred-team', byId, 'team-p', ['team-p', 'team-s'])
    ).toEqual(['team-s'])
  })

  it('uses personal workspace for user credentials', () => {
    expect(
      resolvePlaygroundVirtualKeyTeamIds('cred-user', byId, 'team-p', ['team-p', 'team-s'])
    ).toEqual(['team-p'])
  })
})

describe('listPlaygroundCredentialSummariesFallback', () => {
  it('merges personal and team summaries without duplicate ids', async () => {
    listMyCredentialsMock.mockResolvedValue([
      {
        id: 'cred-user',
        provider: 'openai',
        name: 'My',
        scope: 'user',
        is_active: true,
      } as ProviderCredential,
    ])
    listCredentialSummariesMock.mockImplementation((teamId: string) =>
      Promise.resolve(teamId === 'team-s' ? [teamSummary] : [])
    )
    const rows = await listPlaygroundCredentialSummariesFallback([personalTeam, sharedTeam])
    expect(rows.map((r) => r.id).sort()).toEqual(['cred-team', 'cred-user'])
  })
})
