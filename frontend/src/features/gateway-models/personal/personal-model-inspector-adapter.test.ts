import { describe, expect, it } from 'vitest'

import {
  personalModelInspectorContext,
  personalModelToInspectorModel,
} from './personal-model-inspector-adapter'

describe('personal-model-inspector-adapter', () => {
  const model = {
    id: 'pm-1',
    user_id: 'user-1',
    display_name: 'My GPT',
    provider: 'openai',
    model_id: 'gpt-4o',
    api_key_masked: 'sk-***',
    has_api_key: true,
    api_base: null,
    credential_id: 'cred-1',
    model_types: ['text', 'image'] as const,
    config: null,
    is_active: true,
    is_system: false,
    capability: 'chat',
    name: 'personal/openai/gpt-4o',
    selector_capabilities: { supports_vision: true },
    last_test_status: 'success' as const,
    last_tested_at: null,
    last_test_reason: null,
    created_at: '2026-01-01T00:00:00.000Z',
    updated_at: null,
  }

  it('maps personal model to inspector gateway shape', () => {
    const mapped = personalModelToInspectorModel(model)
    expect(mapped).toMatchObject({
      id: 'pm-1',
      name: 'personal/openai/gpt-4o',
      real_model: 'gpt-4o',
      enabled: true,
      capability: 'chat',
      model_types: ['text', 'image'],
      credential_id: 'cred-1',
      created_by_user_id: 'user-1',
    })
  })

  it('extracts personal inspector context', () => {
    expect(personalModelInspectorContext(model)).toEqual({
      displayName: 'My GPT',
      userId: 'user-1',
    })
  })
})
