import { describe, expect, it } from 'vitest'

import type { GatewayModel } from '@/api/gateway/models'
import type { PersonalGatewayModel } from '@/api/gateway/my-models'

import { fromGatewayModel, fromPersonalModel } from './adapters'
import {
  gatewayModelDisplayName,
  gatewayModelLabel,
  personalModelDisplayName,
} from './gateway-model-display-name'
import { clientInvokeModelName, listDisplayName } from './model-list-columns'

function personalModel(
  partial: Partial<PersonalGatewayModel> & Pick<PersonalGatewayModel, 'id'>
): PersonalGatewayModel {
  return {
    user_id: 'u1',
    display_name: 'My Model',
    provider: 'openai',
    model_id: 'gpt-4o',
    api_key_masked: 'sk-***',
    has_api_key: true,
    api_base: null,
    credential_id: 'c1',
    model_types: ['text'],
    config: null,
    is_active: true,
    is_system: false,
    capability: 'chat',
    name: 'personal/openai/gpt-4o',
    last_test_status: null,
    last_tested_at: null,
    last_test_reason: null,
    created_at: '2026-01-01T00:00:00.000Z',
    updated_at: null,
    ...partial,
  }
}

function gatewayModel(partial: Partial<GatewayModel> & Pick<GatewayModel, 'id'>): GatewayModel {
  return {
    tenant_id: 't1',
    team_id: 't1',
    name: 'alias/gpt',
    capability: 'chat',
    real_model: 'gpt-4o-mini',
    credential_id: 'c2',
    provider: 'openai',
    weight: 1,
    rpm_limit: null,
    tpm_limit: null,
    enabled: true,
    last_test_status: null,
    last_tested_at: null,
    last_test_reason: null,
    created_at: '2026-01-01T00:00:00.000Z',
    ...partial,
  }
}

describe('gateway-model-display-name', () => {
  it('reads personal display_name', () => {
    expect(personalModelDisplayName(personalModel({ id: 'p1' }))).toBe('My Model')
  })

  it('reads team/system tags.display_name with name fallback', () => {
    expect(
      gatewayModelDisplayName(gatewayModel({ id: 'g1', tags: { display_name: 'GPT-4o 生产' } }))
    ).toBe('GPT-4o 生产')
    expect(gatewayModelDisplayName(gatewayModel({ id: 'g2', name: 'glm-5.1' }))).toBe('glm-5.1')
  })

  it('gatewayModelLabel falls back to name', () => {
    expect(gatewayModelLabel(gatewayModel({ id: 'g3', name: 'team/qwen' }))).toBe('team/qwen')
    expect(
      gatewayModelLabel(
        gatewayModel({ id: 'g4', name: 'team/qwen', tags: { display_name: '通义千问' } })
      )
    ).toBe('通义千问')
  })
})

describe('listDisplayName', () => {
  it('shows personal display_name when different from invoke route', () => {
    const item = fromPersonalModel(personalModel({ id: 'p1', display_name: 'My GPT' }))
    expect(listDisplayName(item)).toBe('My GPT')
    expect(clientInvokeModelName(item)).toBe('personal/openai/gpt-4o')
  })

  it('shows team display name from tags or registration alias', () => {
    const tagged = fromGatewayModel(
      gatewayModel({
        id: 'g1',
        name: 'team/gpt-4o',
        tags: { display_name: 'GPT-4o 生产环境' },
      }),
      'team'
    )
    expect(listDisplayName(tagged)).toBe('GPT-4o 生产环境')

    const aliasOnly = fromGatewayModel(gatewayModel({ id: 'g2', name: 'glm-5.1' }), 'team')
    expect(listDisplayName(aliasOnly)).toBe('glm-5.1')
    expect(clientInvokeModelName(aliasOnly)).toBe('glm-5.1')
  })

  it('shows team tags.display_name even when equal to invoke name', () => {
    const item = fromGatewayModel(
      gatewayModel({
        id: 'g3',
        name: 'team/qwen',
        tags: { display_name: 'team/qwen' },
      }),
      'team'
    )
    expect(listDisplayName(item)).toBe('team/qwen')
  })
})
