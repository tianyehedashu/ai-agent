import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { GatewayModel } from '@/api/gateway'

import { ModelCapabilityBadges } from './model-capability-badges'

function baseModel(overrides: Partial<GatewayModel> = {}): GatewayModel {
  return {
    id: 'm1',
    team_id: null,
    name: 'demo',
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
    created_at: '2026-01-01T00:00:00Z',
    ...overrides,
  } as GatewayModel
}

describe('ModelCapabilityBadges context window', () => {
  it('renders context window from selector_capabilities', () => {
    render(
      <ModelCapabilityBadges
        model={baseModel({ selector_capabilities: { context_window: 262144 } })}
      />
    )
    expect(screen.getByText('上下文 256K')).toBeInTheDocument()
  })

  it('falls back to tags when selector_capabilities missing', () => {
    render(<ModelCapabilityBadges model={baseModel({ tags: { context_window: 1000000 } })} />)
    expect(screen.getByText('上下文 1M')).toBeInTheDocument()
  })

  it('formats non-power-of-two windows as rounded K', () => {
    render(
      <ModelCapabilityBadges
        model={baseModel({ selector_capabilities: { context_window: 200000 } })}
      />
    )
    expect(screen.getByText('上下文 200K')).toBeInTheDocument()
  })

  it('omits badge when context window unknown', () => {
    render(
      <ModelCapabilityBadges model={baseModel({ selector_capabilities: { context_window: 0 } })} />
    )
    expect(screen.queryByText(/上下文/)).not.toBeInTheDocument()
  })
})
