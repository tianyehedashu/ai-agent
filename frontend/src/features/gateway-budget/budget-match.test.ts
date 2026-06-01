import { describe, expect, it } from 'vitest'

import type { GatewayBudget } from '@/api/gateway/budgets'

import { matchBudgetsForContext } from './budget-match'
import { quotaListParamsForContext } from './quota-rule-utils'

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

describe('matchBudgetsForContext (legacy)', () => {
  it('matches team model tenant budgets by model name', () => {
    const rows = [
      budget({ id: '1', target_kind: 'tenant', model_name: 'gpt-4' }),
      budget({ id: '2', target_kind: 'tenant', model_name: 'claude-3' }),
      budget({ id: '3', target_kind: 'tenant', model_name: null }),
    ]
    // eslint-disable-next-line @typescript-eslint/no-deprecated -- legacy budget matcher regression
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
    // eslint-disable-next-line @typescript-eslint/no-deprecated -- legacy budget matcher regression
    const matched = matchBudgetsForContext(rows, { kind: 'virtual_key', keyId: 'key-a' })
    expect(matched.map((b) => b.id)).toEqual(['k1'])
  })
})

describe('quotaListParamsForContext', () => {
  it('narrows personal context to user_id', () => {
    expect(
      quotaListParamsForContext({ kind: 'personal', userId: 'u1', modelNames: ['gpt-4'] })
    ).toEqual({ user_id: 'u1', include_usage: true })
  })

  it('narrows team_model context to model_name', () => {
    expect(
      quotaListParamsForContext({ kind: 'team_model', modelName: 'claude-3', userId: 'u1' })
    ).toEqual({ model_name: 'claude-3', include_usage: true })
  })

  it('falls back to usage-only fetch for credential context', () => {
    expect(
      quotaListParamsForContext({
        kind: 'credential',
        userId: 'u1',
        linkedModelNames: ['m1'],
      })
    ).toEqual({ include_usage: true })
  })
})
