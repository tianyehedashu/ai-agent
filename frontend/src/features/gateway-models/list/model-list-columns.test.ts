import { describe, expect, it } from 'vitest'

import { listContextWindowLabel } from '@/features/gateway-models/context-window-display'
import { fromGatewayModel, fromPersonalModel } from '@/features/gateway-models/list/adapters'
import {
  clientInvokeModelName,
  listCapabilityLabel,
  listCredentialName,
  listDisplayName,
} from '@/features/gateway-models/list/model-list-columns'

describe('model-list-columns', () => {
  it('uses route name as personal client invoke name', () => {
    const item = fromPersonalModel({
      id: 'p1',
      user_id: 'u1',
      display_name: 'My GPT',
      name: 'personal/openai/gpt-4o',
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
      last_test_status: null,
      last_tested_at: null,
      last_test_reason: null,
      created_at: '2026-01-01T00:00:00.000Z',
      updated_at: null,
    })
    expect(clientInvokeModelName(item)).toBe('personal/openai/gpt-4o')
    expect(listDisplayName(item)).toBe('My GPT')
  })

  it('uses model name as team client invoke name', () => {
    const item = fromGatewayModel(
      {
        id: 'g1',
        tenant_id: 't1',
        team_id: 't1',
        name: 'team/gpt-4o',
        capability: 'chat',
        real_model: 'gpt-4o-mini',
        credential_id: 'c1',
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
    expect(clientInvokeModelName(item)).toBe('team/gpt-4o')
    expect(listDisplayName(item)).toBe('team/gpt-4o')
  })

  it('resolves capability and credential labels', () => {
    const item = fromGatewayModel(
      {
        id: 'g2',
        tenant_id: 't1',
        team_id: 't1',
        name: 'team/embed',
        capability: 'embedding',
        real_model: 'text-embedding-3',
        credential_id: 'c2',
        credential_name: 'Embed Key',
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
    expect(listCapabilityLabel(item)).toBe('向量')
    expect(listCredentialName(item)).toBe('Embed Key')
  })

  it('joins primary capability with model type labels', () => {
    const item = fromPersonalModel({
      id: 'p2',
      user_id: 'u1',
      display_name: 'Multi',
      name: 'personal/openai/gpt-4o',
      provider: 'openai',
      model_id: 'gpt-4o',
      api_key_masked: 'sk-***',
      has_api_key: true,
      api_base: null,
      credential_id: 'c1',
      model_types: ['text', 'image'],
      config: null,
      is_active: true,
      is_system: false,
      capability: 'chat',
      last_test_status: null,
      last_tested_at: null,
      last_test_reason: null,
      created_at: '2026-01-01T00:00:00.000Z',
      updated_at: null,
    })
    expect(listCapabilityLabel(item)).toBe('聊天 · 文本 · 图片理解')
  })

  it('resolves context window label for list column', () => {
    const item = fromGatewayModel(
      {
        id: 'g3',
        tenant_id: 't1',
        team_id: 't1',
        name: 'team/kimi',
        capability: 'chat',
        real_model: 'kimi-k2',
        credential_id: 'c1',
        provider: 'volcengine',
        weight: 1,
        rpm_limit: null,
        tpm_limit: null,
        enabled: true,
        selector_capabilities: { context_window: 131072 },
        last_test_status: null,
        last_tested_at: null,
        last_test_reason: null,
        created_at: '2026-01-01T00:00:00.000Z',
      },
      'team'
    )
    expect(listContextWindowLabel(item)).toBe('128K')
  })
})
