import { describe, expect, it } from 'vitest'

import type { GatewayModel, UpstreamPricingRow } from '@/api/gateway'

import {
  buildLinkedModelKeys,
  buildUpstreamPricingKeySet,
  filterUpstreamRows,
  findModelsMissingUpstream,
  upstreamPricingKey,
} from './upstream-pricing-view'

const baseModel = (overrides: Partial<GatewayModel>): GatewayModel => ({
  id: 'm1',
  tenant_id: overrides.tenant_id ?? overrides.team_id ?? 't1',
  team_id: overrides.team_id ?? 't1',
  name: 'gpt-mini',
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
  created_at: '2026-01-01T00:00:00Z',
  ...overrides,
})

const baseRow = (overrides: Partial<UpstreamPricingRow>): UpstreamPricingRow => ({
  id: 'p1',
  provider: 'openai',
  upstream_model: 'gpt-4o-mini',
  capability: 'chat',
  input_cost_per_token_usd: '0',
  output_cost_per_token_usd: '0',
  effective_from: '2026-01-01T00:00:00Z',
  effective_to: null,
  version: 1,
  source: 'litellm',
  ...overrides,
})

describe('upstreamPricingKey', () => {
  it('normalizes empty capability to chat', () => {
    expect(upstreamPricingKey('openai', 'gpt-4o-mini', '')).toBe(
      upstreamPricingKey('openai', 'gpt-4o-mini', 'chat')
    )
  })
})

describe('filterUpstreamRows', () => {
  it('keeps only linked models when onlyLinkedModels is true', () => {
    const linkedKeys = buildLinkedModelKeys([baseModel({})])
    const rows = [
      baseRow({}),
      baseRow({ id: 'p2', upstream_model: 'orphan-image-key', provider: 'openai' }),
    ]
    const filtered = filterUpstreamRows(rows, {
      effectiveProviders: new Set(['openai']),
      linkedKeys,
      onlyLinkedModels: true,
      selectedProviders: new Set(),
    })
    expect(filtered).toHaveLength(1)
    expect(filtered[0].upstream_model).toBe('gpt-4o-mini')
  })
})

describe('findModelsMissingUpstream', () => {
  it('lists enabled models without a matching upstream row', () => {
    const missing = findModelsMissingUpstream(
      [
        baseModel({ name: 'alias-a' }),
        baseModel({ id: 'm2', name: 'alias-b', real_model: 'gpt-4o' }),
      ],
      buildUpstreamPricingKeySet([baseRow({})])
    )
    expect(missing).toHaveLength(1)
    expect(missing[0].gatewayName).toBe('alias-b')
    expect(missing[0].upstreamModel).toBe('gpt-4o')
  })
})
