import { describe, expect, it } from 'vitest'

import type { GatewayTeam } from '@/api/gateway/teams'
import {
  buildCopyModelsToTeamBody,
  buildDestinationTeamOptions,
  groupSelectedModelsForCopy,
  isCopyModelsPlanValid,
} from '@/features/gateway-models/copy-models-to-team-utils'
import { fromGatewayModel, fromPersonalModel } from '@/features/gateway-models/list/adapters'
import type { GatewayModelListItem } from '@/features/gateway-models/list/types'

function team(id: string): GatewayTeam {
  return {
    id,
    name: `Team ${id}`,
    slug: id,
    kind: 'shared',
    owner_user_id: 'owner',
    team_role: 'member',
  }
}

function personalItem(id: string, credId: string): GatewayModelListItem {
  return fromPersonalModel({
    id,
    user_id: 'user-1',
    display_name: 'Personal',
    provider: 'openai',
    model_id: 'gpt-4o',
    api_key_masked: 'sk-***',
    has_api_key: true,
    api_base: null,
    credential_id: credId,
    model_types: ['text'],
    config: null,
    is_active: true,
    is_system: false,
    capability: 'chat',
    name: 'personal/openai/gpt',
    last_test_status: null,
    last_tested_at: null,
    last_test_reason: null,
    created_at: '2026-01-01T00:00:00.000Z',
    updated_at: null,
  })
}

function teamItem(id: string, credId: string, teamId: string): GatewayModelListItem {
  return fromGatewayModel(
    {
      id,
      tenant_id: teamId,
      team_id: teamId,
      name: 'alias/model',
      capability: 'chat',
      real_model: 'gpt-4o-mini',
      credential_id: credId,
      provider: 'openai',
      weight: 1,
      rpm_limit: null,
      tpm_limit: null,
      enabled: true,
      last_test_status: null,
      last_tested_at: null,
      last_test_reason: null,
      created_at: '2026-01-01T00:00:00.000Z',
    },
    'team'
  )
}

describe('groupSelectedModelsForCopy', () => {
  it('groups by credential id', () => {
    const groups = groupSelectedModelsForCopy([
      personalItem('m1', 'c1'),
      personalItem('m2', 'c1'),
      teamItem('m3', 'c2', 't1'),
    ])
    expect(groups).toHaveLength(2)
    const byCred = Object.fromEntries(groups.map((g) => [g.sourceCredentialId, g.modelIds]))
    expect(byCred.c1).toEqual(['m1', 'm2'])
    expect(byCred.c2).toEqual(['m3'])
  })
})

describe('buildDestinationTeamOptions', () => {
  it('excludes source and personal teams', () => {
    const options = buildDestinationTeamOptions(
      [team('t1'), team('t2'), team('personal')],
      ['t1'],
      'personal'
    )
    expect(options.map((t) => t.id)).toEqual(['t2'])
  })
})

describe('buildCopyModelsToTeamBody', () => {
  it('builds existing credential plan', () => {
    const items = [personalItem('m1', 'c1')]
    const body = buildCopyModelsToTeamBody(items, 'dest-team', {
      c1: { mode: 'existing', destinationCredentialId: 'dest-cred' },
    })
    expect(body).toEqual({
      model_ids: ['m1'],
      destination_team_id: 'dest-team',
      credential_plans: [
        {
          source_credential_id: 'c1',
          mode: 'existing',
          destination_credential_id: 'dest-cred',
        },
      ],
    })
  })
})

describe('isCopyModelsPlanValid', () => {
  it('requires destination credential for existing mode', () => {
    const groups = groupSelectedModelsForCopy([personalItem('m1', 'c1')])
    expect(
      isCopyModelsPlanValid(groups, {
        c1: { mode: 'existing', destinationCredentialId: null },
      })
    ).toBe(false)
    expect(
      isCopyModelsPlanValid(groups, {
        c1: { mode: 'copy_credential', destinationCredentialId: null },
      })
    ).toBe(true)
  })
})
