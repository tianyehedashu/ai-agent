import { describe, expect, it } from 'vitest'

import type { PlaygroundCredentialSummary } from '@/api/gateway'
import type { GatewayModel } from '@/api/gateway/models'
import type { PersonalGatewayModel } from '@/api/gateway/my-models'

import {
  filterPlaygroundCredentialOptions,
  groupPlaygroundCredentialOptions,
  isPersonalPlaygroundCredential,
  isPlaygroundCredentialSelectable,
  resolvePlaygroundContextTeamId,
} from './playground-credential-options'
import { buildPlaygroundCandidateModels } from './playground-model-sources'

const teamSummary: PlaygroundCredentialSummary = {
  id: 'cred-team',
  provider: 'openai',
  name: 'Team OpenAI',
  scope: 'team',
  is_active: true,
  is_config_managed: false,
  context_team_id: 'team-a',
}

const inactiveTeamSummary: PlaygroundCredentialSummary = {
  ...teamSummary,
  id: 'cred-team-off',
  name: 'Team Off',
  is_active: false,
}

const systemSummary: PlaygroundCredentialSummary = {
  id: 'cred-sys',
  provider: 'anthropic',
  name: 'Platform Anthropic',
  scope: 'system',
  is_active: true,
  is_config_managed: true,
  context_team_id: 'team-personal',
}

const personalSummary: PlaygroundCredentialSummary = {
  id: 'cred-user',
  provider: 'openai',
  name: 'My OpenAI',
  scope: 'user',
  is_active: true,
  is_config_managed: false,
  context_team_id: 'team-personal',
}

describe('isPlaygroundCredentialSelectable', () => {
  const membership = new Set(['team-a', 'team-personal'])

  it('allows active user and in-membership team/system credentials', () => {
    expect(isPlaygroundCredentialSelectable(personalSummary, membership)).toBe(true)
    expect(isPlaygroundCredentialSelectable(teamSummary, membership)).toBe(true)
    expect(isPlaygroundCredentialSelectable(systemSummary, membership)).toBe(true)
  })

  it('rejects inactive and out-of-membership team credentials', () => {
    expect(isPlaygroundCredentialSelectable(inactiveTeamSummary, membership)).toBe(false)
    expect(
      isPlaygroundCredentialSelectable(
        { ...teamSummary, id: 'foreign', context_team_id: 'team-foreign' },
        membership
      )
    ).toBe(false)
  })
})

describe('filterPlaygroundCredentialOptions', () => {
  const membership = new Set(['team-a', 'team-personal'])

  it('keeps active credentials in membership only', () => {
    const outOfMembership: PlaygroundCredentialSummary = {
      ...teamSummary,
      id: 'cred-other-team',
      context_team_id: 'team-foreign',
    }
    const filtered = filterPlaygroundCredentialOptions(
      [teamSummary, inactiveTeamSummary, outOfMembership],
      membership
    )
    expect(filtered.map((c) => c.id)).toEqual(['cred-team'])
  })

  it('excludes inactive credentials even when previously selected', () => {
    const filtered = filterPlaygroundCredentialOptions(
      [teamSummary, inactiveTeamSummary],
      membership
    )
    expect(filtered.map((c) => c.id)).toEqual(['cred-team'])
  })
})

describe('groupPlaygroundCredentialOptions', () => {
  it('groups by scope and sorts by name', () => {
    const grouped = groupPlaygroundCredentialOptions([systemSummary, teamSummary, personalSummary])
    expect(grouped.personal.map((c) => c.id)).toEqual(['cred-user'])
    expect(grouped.team.map((c) => c.id)).toEqual(['cred-team'])
    expect(grouped.system.map((c) => c.id)).toEqual(['cred-sys'])
  })
})

describe('resolvePlaygroundContextTeamId', () => {
  const byId = new Map([
    [teamSummary.id, teamSummary],
    [personalSummary.id, personalSummary],
    [systemSummary.id, systemSummary],
  ])

  it('uses workspace team when no credential selected', () => {
    expect(resolvePlaygroundContextTeamId('', byId, 'team-personal')).toBe('team-personal')
  })

  it('uses credential context for team/system credentials', () => {
    expect(resolvePlaygroundContextTeamId('cred-team', byId, 'team-personal')).toBe('team-a')
    expect(resolvePlaygroundContextTeamId('cred-sys', byId, 'team-personal')).toBe('team-personal')
  })

  it('uses workspace team for personal credential', () => {
    expect(resolvePlaygroundContextTeamId('cred-user', byId, 'team-personal')).toBe('team-personal')
  })
})

describe('isPersonalPlaygroundCredential', () => {
  it('detects user-scope credential', () => {
    const byId = new Map([
      [personalSummary.id, personalSummary],
      [teamSummary.id, teamSummary],
    ])
    expect(isPersonalPlaygroundCredential(byId, 'cred-user')).toBe(true)
    expect(isPersonalPlaygroundCredential(byId, 'cred-team')).toBe(false)
  })
})

describe('buildPlaygroundCandidateModels', () => {
  const teamModel = {
    id: 'm-team',
    name: 'team-model',
    capability: 'chat',
    provider: 'openai',
    last_test_status: 'success' as const,
    enabled: true,
    selector_capabilities: {},
    model_types: ['chat'],
  } as unknown as GatewayModel

  const personalModel = {
    id: 'm-personal',
    name: 'my-model',
    display_name: 'my-model',
    capability: 'chat',
    provider: 'volcengine',
    last_test_status: 'success' as const,
    is_active: true,
    credential_id: 'cred-user',
    selector_capabilities: {},
    model_types: ['chat'],
  } as unknown as PersonalGatewayModel

  it('merges team and personal models when no credential filter', () => {
    const result = buildPlaygroundCandidateModels({
      credentialId: '',
      isPersonalCredential: false,
      teamModels: [teamModel],
      myModels: [personalModel],
    })
    expect(result.map((m) => m.name).sort()).toEqual(['my-model', 'team-model'])
  })

  it('returns only team models for team credential filter', () => {
    const result = buildPlaygroundCandidateModels({
      credentialId: 'cred-team',
      isPersonalCredential: false,
      teamModels: [teamModel],
      myModels: [personalModel],
    })
    expect(result.map((m) => m.name)).toEqual(['team-model'])
    expect(result.every((m) => m.scope === 'team')).toBe(true)
  })

  it('returns only matching personal models for user credential filter', () => {
    const result = buildPlaygroundCandidateModels({
      credentialId: 'cred-user',
      isPersonalCredential: true,
      teamModels: [teamModel],
      myModels: [personalModel],
    })
    expect(result.map((m) => m.name)).toEqual(['my-model'])
    expect(result.every((m) => m.scope === 'personal')).toBe(true)
  })
})
