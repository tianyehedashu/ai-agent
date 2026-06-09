/**
 * @see constants.ts
 */

import { describe, expect, it } from 'vitest'

import {
  CAPABILITY_LABELS,
  ROUTING_STRATEGY_LABELS,
  capabilityLabel,
  routingStrategyLabel,
} from './constants'

describe('capabilityLabel', () => {
  it('returns Chinese label for known capability', () => {
    expect(capabilityLabel('chat')).toBe(CAPABILITY_LABELS.chat)
    expect(capabilityLabel('embedding')).toBe('向量 Embedding')
  })

  it('falls back to raw value for unknown capability', () => {
    expect(capabilityLabel('custom_cap')).toBe('custom_cap')
  })
})

describe('routingStrategyLabel', () => {
  it('returns Chinese label for known strategy', () => {
    expect(routingStrategyLabel('simple-shuffle')).toBe(ROUTING_STRATEGY_LABELS['simple-shuffle'])
    expect(routingStrategyLabel('weighted-pick')).toBe('按权重路由')
    expect(routingStrategyLabel('usage-based-routing-v2')).toBe('按用量路由')
    expect(routingStrategyLabel('cost-based-routing')).toBe('按成本路由')
  })

  it('returns Chinese label for legacy strategy value', () => {
    expect(routingStrategyLabel('usage-based-routing')).toBe('按用量路由')
  })

  it('falls back to raw value for unknown strategy', () => {
    expect(routingStrategyLabel('custom-strategy')).toBe('custom-strategy')
  })
})
