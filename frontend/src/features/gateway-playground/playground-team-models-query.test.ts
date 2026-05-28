import { describe, expect, it } from 'vitest'

import type { GatewayModel } from '@/api/gateway/models'

import {
  filterPlaygroundManagedTeamModels,
  shouldQueryManagedTeamModelsForPlayground,
} from './playground-team-models-query'

function model(partial: Partial<GatewayModel> & Pick<GatewayModel, 'id'>): GatewayModel {
  return {
    id: partial.id,
    team_id: partial.team_id ?? null,
    tenant_id: partial.tenant_id ?? partial.team_id ?? null,
    name: partial.name ?? 'm1',
    capability: partial.capability ?? 'chat',
    real_model: partial.real_model ?? 'gpt-4o-mini',
    credential_id: partial.credential_id ?? 'cred-1',
    provider: partial.provider ?? 'openai',
    weight: 1,
    rpm_limit: null,
    tpm_limit: null,
    enabled: true,
    last_test_status: partial.last_test_status ?? 'success',
    last_tested_at: null,
    last_test_reason: null,
    created_at: '2026-01-01T00:00:00Z',
  }
}

describe('shouldQueryManagedTeamModelsForPlayground', () => {
  it('uses managed aggregate for team/system credential filter', () => {
    expect(shouldQueryManagedTeamModelsForPlayground('cred-team', false)).toBe(true)
  })

  it('skips managed aggregate for personal credential or empty filter', () => {
    expect(shouldQueryManagedTeamModelsForPlayground('', false)).toBe(false)
    expect(shouldQueryManagedTeamModelsForPlayground('cred-user', true)).toBe(false)
  })
})

describe('filterPlaygroundManagedTeamModels', () => {
  it('keeps models for selected context team only', () => {
    const items = [
      model({ id: 'a', tenant_id: 'team-a', name: 'a-model' }),
      model({ id: 'b', tenant_id: 'team-b', name: 'b-model' }),
    ]
    expect(filterPlaygroundManagedTeamModels(items, 'team-a').map((m) => m.name)).toEqual([
      'a-model',
    ])
  })

  it('returns all items when context team is unset', () => {
    const items = [model({ id: 'a', tenant_id: 'team-a' })]
    expect(filterPlaygroundManagedTeamModels(items, null)).toHaveLength(1)
  })
})
