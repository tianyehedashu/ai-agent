import { describe, expect, it } from 'vitest'

import { formatPricingEstimateUsd } from './use-pricing-estimate'

describe('formatPricingEstimateUsd', () => {
  it('formats downstream revenue as USD', () => {
    const label = formatPricingEstimateUsd({
      gateway_model_id: 'id',
      hit_chain: ['team'],
      upstream_cost_usd: '0.001',
      downstream_revenue_usd: '0.002',
      margin_usd: '0.001',
      rate_snapshot: {},
      disclaimer: 'estimate_only',
    })
    expect(label).toMatch(/0\.002/)
    expect(label.length).toBeGreaterThan(0)
  })
})
