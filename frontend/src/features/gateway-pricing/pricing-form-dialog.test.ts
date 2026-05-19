import { describe, expect, it } from 'vitest'

import { buildDownstreamPricingPayload, buildUpstreamPricingPayload } from './pricing-form-payloads'

describe('pricing form payload builders', () => {
  it('builds an upstream manual pricing payload', () => {
    expect(
      buildUpstreamPricingPayload(
        {
          provider: 'openai',
          upstream_model: 'openai/gpt-4o-mini',
          capability: 'chat',
          input: '1.5',
          output: '6',
          cache_creation: '',
          cache_read: '0.3',
        },
        'CNY'
      )
    ).toEqual({
      provider: 'openai',
      upstream_model: 'openai/gpt-4o-mini',
      capability: 'chat',
      currency: 'CNY',
      amount_per_million: {
        input: 1.5,
        output: 6,
        cache_creation: null,
        cache_read: 0.3,
      },
    })
  })

  it('builds a downstream mirror payload', () => {
    expect(
      buildDownstreamPricingPayload(
        {
          gateway_model_id: 'model-id',
          inheritance_strategy: 'mirror',
          input: '',
          output: '',
          cache_creation: '',
          cache_read: '',
          per_request: '',
        },
        'USD'
      )
    ).toEqual({
      scope: 'team',
      gateway_model_id: 'model-id',
      inheritance_strategy: 'mirror',
      currency: 'USD',
      amount_per_million: null,
    })
  })

  it('builds a downstream manual pricing payload', () => {
    expect(
      buildDownstreamPricingPayload(
        {
          gateway_model_id: 'model-id',
          inheritance_strategy: 'manual',
          input: '2',
          output: '8',
          cache_creation: '1',
          cache_read: '',
          per_request: '0.01',
        },
        'CNY'
      )
    ).toEqual({
      scope: 'team',
      gateway_model_id: 'model-id',
      inheritance_strategy: 'manual',
      currency: 'CNY',
      amount_per_million: {
        input: 2,
        output: 8,
        cache_creation: 1,
        cache_read: null,
        per_request: 0.01,
      },
    })
  })
})
