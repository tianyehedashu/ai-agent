import { describe, expect, it } from 'vitest'

import { fromGatewayModel } from '@/features/gateway-models/list/adapters'

import {
  contextWindowEditorValue,
  formatContextWindow,
  listContextWindowLabel,
  resolveContextWindow,
} from './context-window-display'

describe('context-window-display', () => {
  it('formats power-of-two token counts', () => {
    expect(formatContextWindow(262144)).toBe('256K')
    expect(formatContextWindow(1_000_000)).toBe('1M')
  })

  it('resolves context window from selector_capabilities', () => {
    expect(resolveContextWindow({ context_window: 131072 })).toBe(131072)
    expect(resolveContextWindow({ context_window: 0 })).toBe(0)
    expect(resolveContextWindow(undefined, { context_window: 32000 })).toBe(32000)
  })

  it('formats editor value from capabilities or tags', () => {
    expect(contextWindowEditorValue({ context_window: 262144 })).toBe('262144')
    expect(contextWindowEditorValue(undefined, { context_window: 32000 })).toBe('32000')
    expect(contextWindowEditorValue({ context_window: 0 })).toBe('')
  })

  it('formats list column label', () => {
    const item = fromGatewayModel(
      {
        id: 'g1',
        tenant_id: 't1',
        team_id: 't1',
        name: 'team/gpt',
        capability: 'chat',
        real_model: 'gpt-4o',
        credential_id: 'c1',
        provider: 'openai',
        weight: 1,
        rpm_limit: null,
        tpm_limit: null,
        enabled: true,
        selector_capabilities: { context_window: 262144 },
        last_test_status: null,
        last_tested_at: null,
        last_test_reason: null,
        created_at: '2026-01-01T00:00:00.000Z',
      },
      'team'
    )
    expect(listContextWindowLabel(item)).toBe('256K')
  })

  it('returns dash label when context window unset', () => {
    const item = fromGatewayModel(
      {
        id: 'g2',
        tenant_id: 't1',
        team_id: 't1',
        name: 'team/gpt',
        capability: 'chat',
        real_model: 'gpt-4o',
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
    expect(listContextWindowLabel(item)).toBe('—')
  })
})
