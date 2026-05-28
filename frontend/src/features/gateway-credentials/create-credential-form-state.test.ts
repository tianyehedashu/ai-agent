/**
 * @see create-credential-form-state.ts
 */

import { describe, expect, it } from 'vitest'

import type { GatewayTeam } from '@/api/gateway/teams'

import {
  buildCreateCredentialFormState,
  resolveInitialTeamId,
  shouldInitializeCreateCredentialForm,
} from './create-credential-form-state'

const teamA: GatewayTeam = {
  id: 'team-a',
  name: 'Team A',
  kind: 'shared',
  slug: 'team-a',
  owner_user_id: 'user-1',
}

const teamB: GatewayTeam = {
  id: 'team-b',
  name: 'Team B',
  kind: 'shared',
  slug: 'team-b',
  owner_user_id: 'user-1',
}

describe('resolveInitialTeamId', () => {
  it('prefers defaultTeamId when present in writable teams', () => {
    expect(resolveInitialTeamId([teamA, teamB], 'team-b')).toBe('team-b')
  })

  it('falls back to first writable team when default is missing', () => {
    expect(resolveInitialTeamId([teamA, teamB], undefined)).toBe('team-a')
  })

  it('falls back to first writable team when default is not writable', () => {
    expect(resolveInitialTeamId([teamA], 'team-b')).toBe('team-a')
  })
})

describe('buildCreateCredentialFormState', () => {
  it('builds empty form with team scope defaults', () => {
    const state = buildCreateCredentialFormState({
      resolvedDefaultScope: 'team',
      defaultTeamId: 'team-b',
      teamOptions: [teamA, teamB],
    })

    expect(state.scope).toBe('team')
    expect(state.teamId).toBe('team-b')
    expect(state.provider).toBeTruthy()
    expect(state.name).toBe('')
    expect(state.apiKey).toBe('')
    expect(state.extra).toEqual({})
  })

  it('honors defaultProvider when valid for scope', () => {
    const state = buildCreateCredentialFormState({
      resolvedDefaultScope: 'user',
      defaultProvider: 'deepseek',
      teamOptions: [],
    })

    expect(state.provider).toBe('deepseek')
  })
})

describe('shouldInitializeCreateCredentialForm', () => {
  it('initializes only on open transition', () => {
    expect(shouldInitializeCreateCredentialForm(true, false)).toBe(true)
    expect(shouldInitializeCreateCredentialForm(true, true)).toBe(false)
    expect(shouldInitializeCreateCredentialForm(false, true)).toBe(false)
    expect(shouldInitializeCreateCredentialForm(false, false)).toBe(false)
  })
})
