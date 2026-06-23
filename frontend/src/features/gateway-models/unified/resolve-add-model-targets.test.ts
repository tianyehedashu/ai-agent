import { describe, expect, it } from 'vitest'

import {
  resolveAddModelTargets,
  type ResolveAddModelTargetsInput,
} from './resolve-add-model-targets'

const ROUTE_TEAM = 'route-team'
const TEAM_A = 'team-a'
const TEAM_B = 'team-b'

function baseInput(
  overrides: Partial<ResolveAddModelTargetsInput> = {}
): ResolveAddModelTargetsInput {
  return {
    scopeFilter: 'all' as const,
    routeTeamId: ROUTE_TEAM,
    canRegisterTeam: true,
    isPlatformAdmin: false,
    eligibleTeamIds: new Set([TEAM_A, TEAM_B]),
    defaultRegisterTeamId: TEAM_A,
    ...overrides,
  }
}

describe('resolveAddModelTargets', () => {
  it('returns personal, team, and system when scope is all and admin', () => {
    const targets = resolveAddModelTargets(baseInput({ isPlatformAdmin: true }))
    expect(targets.map((t) => t.scope)).toEqual(['personal', 'team', 'system'])
    expect(targets[0]?.href).toContain('scope=personal')
    expect(targets[1]?.href).toContain('scope=team')
    expect(targets[1]?.href).toContain(`/teams/${TEAM_A}/`)
    expect(targets[2]?.href).toContain('scope=system')
  })

  it('returns personal and team only for non-admin on all scope', () => {
    const targets = resolveAddModelTargets(baseInput())
    expect(targets.map((t) => t.scope)).toEqual(['personal', 'team'])
  })

  it('omits team when cannot register team', () => {
    const targets = resolveAddModelTargets(baseInput({ canRegisterTeam: false }))
    expect(targets.map((t) => t.scope)).toEqual(['personal'])
  })

  it('omits team when no register team id', () => {
    const targets = resolveAddModelTargets(baseInput({ defaultRegisterTeamId: undefined }))
    expect(targets.map((t) => t.scope)).toEqual(['personal'])
  })

  it('prefers affiliationTeamId when eligible', () => {
    const targets = resolveAddModelTargets(baseInput({ affiliationTeamId: TEAM_B }))
    expect(targets.find((t) => t.scope === 'team')?.href).toContain(`/teams/${TEAM_B}/`)
  })

  it('ignores affiliationTeamId not in eligible list', () => {
    const targets = resolveAddModelTargets(baseInput({ affiliationTeamId: 'unknown-team' }))
    expect(targets.find((t) => t.scope === 'team')?.href).toContain(`/teams/${TEAM_A}/`)
  })

  it('includes credentialId in href when provided', () => {
    const targets = resolveAddModelTargets(baseInput({ credentialId: 'cred-1' }))
    expect(targets[0]?.href).toContain('credentialId=cred-1')
    expect(targets[1]?.href).toContain('credentialId=cred-1')
  })

  it('returns single personal target for personal scope', () => {
    const targets = resolveAddModelTargets(baseInput({ scopeFilter: 'personal' }))
    expect(targets).toHaveLength(1)
    expect(targets[0]?.scope).toBe('personal')
  })

  it('returns single team target for team scope', () => {
    const targets = resolveAddModelTargets(
      baseInput({ scopeFilter: 'team', affiliationTeamId: TEAM_B })
    )
    expect(targets).toHaveLength(1)
    expect(targets[0]?.scope).toBe('team')
    expect(targets[0]?.href).toContain(`/teams/${TEAM_B}/`)
  })

  it('returns empty for team scope without register team', () => {
    const targets = resolveAddModelTargets(
      baseInput({
        scopeFilter: 'team',
        canRegisterTeam: false,
      })
    )
    expect(targets).toHaveLength(0)
  })

  it('returns single system target for system scope when admin', () => {
    const targets = resolveAddModelTargets(
      baseInput({ scopeFilter: 'system', isPlatformAdmin: true })
    )
    expect(targets).toHaveLength(1)
    expect(targets[0]?.scope).toBe('system')
  })

  it('returns empty for system scope when not admin', () => {
    const targets = resolveAddModelTargets(
      baseInput({ scopeFilter: 'system', isPlatformAdmin: false })
    )
    expect(targets).toHaveLength(0)
  })
})
