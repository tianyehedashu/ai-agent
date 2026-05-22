import { describe, expect, it } from 'vitest'

import type { CredentialSummary, ProviderCredential } from '@/api/gateway'
import type { GatewayModel } from '@/api/gateway/models'
import type { PersonalGatewayModel } from '@/api/gateway/my-models'

import {
  filterPlaygroundCredentialOptions,
  groupPlaygroundCredentialOptions,
  isPersonalPlaygroundCredential,
  mergePlaygroundCredentialOptions,
  personalCredentialToSummary,
} from './playground-credential-options'
import { buildPlaygroundCandidateModels } from './playground-model-sources'

const teamSummary: CredentialSummary = {
  id: 'cred-team',
  provider: 'openai',
  name: 'Team OpenAI',
  scope: 'team',
  is_active: true,
  is_config_managed: false,
}

const inactiveTeamSummary: CredentialSummary = {
  ...teamSummary,
  id: 'cred-team-off',
  name: 'Team Off',
  is_active: false,
}

const systemSummary: CredentialSummary = {
  id: 'cred-sys',
  provider: 'anthropic',
  name: 'Platform Anthropic',
  scope: 'system',
  is_active: true,
  is_config_managed: true,
}

const personalCredential: ProviderCredential = {
  id: 'cred-user',
  tenant_id: null,
  scope: 'user',
  scope_id: 'user-1',
  provider: 'openai',
  name: 'My OpenAI',
  api_base: null,
  is_active: true,
  extra: null,
  created_at: '2026-01-01T00:00:00Z',
  api_key_masked: 'sk-***',
}

describe('mergePlaygroundCredentialOptions', () => {
  it('merges team summaries and personal credentials without duplicate ids', () => {
    const merged = mergePlaygroundCredentialOptions(
      [teamSummary, systemSummary],
      [personalCredential]
    )
    expect(merged).toHaveLength(3)
    expect(merged.map((c) => c.id).sort()).toEqual(['cred-sys', 'cred-team', 'cred-user'])
  })

  it('maps personal credential to user scope summary', () => {
    expect(personalCredentialToSummary(personalCredential).scope).toBe('user')
  })
})

describe('filterPlaygroundCredentialOptions', () => {
  it('keeps active credentials only by default', () => {
    const filtered = filterPlaygroundCredentialOptions([teamSummary, inactiveTeamSummary], '')
    expect(filtered.map((c) => c.id)).toEqual(['cred-team'])
  })

  it('retains selected inactive credential', () => {
    const filtered = filterPlaygroundCredentialOptions(
      [teamSummary, inactiveTeamSummary],
      inactiveTeamSummary.id
    )
    expect(filtered.map((c) => c.id).sort()).toEqual(['cred-team', 'cred-team-off'])
  })
})

describe('groupPlaygroundCredentialOptions', () => {
  it('groups by scope and sorts by name', () => {
    const grouped = groupPlaygroundCredentialOptions([
      systemSummary,
      teamSummary,
      personalCredentialToSummary(personalCredential),
    ])
    expect(grouped.personal.map((c) => c.id)).toEqual(['cred-user'])
    expect(grouped.team.map((c) => c.id)).toEqual(['cred-team'])
    expect(grouped.system.map((c) => c.id)).toEqual(['cred-sys'])
  })
})

describe('isPersonalPlaygroundCredential', () => {
  it('detects user-scope credential', () => {
    const byId = new Map(
      mergePlaygroundCredentialOptions([], [personalCredential]).map((c) => [c.id, c])
    )
    expect(isPersonalPlaygroundCredential(byId, 'cred-user')).toBe(true)
    expect(isPersonalPlaygroundCredential(byId, 'cred-team')).toBe(false)
  })

  it('accepts credential map lookup', () => {
    const byId = new Map(
      mergePlaygroundCredentialOptions([teamSummary], [personalCredential]).map((c) => [c.id, c])
    )
    expect(isPersonalPlaygroundCredential(byId, 'cred-user')).toBe(true)
    expect(isPersonalPlaygroundCredential(byId, 'cred-team')).toBe(false)
  })
})

describe('buildPlaygroundCandidateModels', () => {
  const teamModel = {
    id: 'm-team',
    name: 'team-model',
    capability: 'chat',
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
