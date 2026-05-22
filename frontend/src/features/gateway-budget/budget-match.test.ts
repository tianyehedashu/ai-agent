import { describe, expect, it } from 'vitest'

import type { GatewayBudget } from '@/api/gateway/budgets'

import { matchBudgetsForContext } from './budget-match'

function budget(partial: Partial<GatewayBudget> & Pick<GatewayBudget, 'id'>): GatewayBudget {
  return {
    target_kind: 'tenant',
    target_id: null,
    period: 'monthly',
    model_name: null,
    limit_usd: 100,
    limit_tokens: null,
    limit_requests: null,
    current_usd: 0,
    current_tokens: 0,
    current_requests: 0,
    reset_at: null,
    ...partial,
  }
}

describe('matchBudgetsForContext', () => {
  it('matches team model tenant budgets by model name', () => {
    const rows = [
      budget({ id: '1', target_kind: 'tenant', model_name: 'gpt-4' }),
      budget({ id: '2', target_kind: 'tenant', model_name: 'claude-3' }),
      budget({ id: '3', target_kind: 'tenant', model_name: null }),
    ]
    const matched = matchBudgetsForContext(rows, {
      kind: 'team_model',
      modelName: 'gpt-4',
    })
    expect(matched.map((b) => b.id)).toEqual(['1', '3'])
  })

  it('matches virtual key budgets', () => {
    const rows = [
      budget({ id: 'k1', target_kind: 'key', target_id: 'key-a' }),
      budget({ id: 'k2', target_kind: 'key', target_id: 'key-b' }),
    ]
    const matched = matchBudgetsForContext(rows, { kind: 'virtual_key', keyId: 'key-a' })
    expect(matched.map((b) => b.id)).toEqual(['k1'])
  })
})
