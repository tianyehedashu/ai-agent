import { describe, expect, it } from 'vitest'

import type { QuotaRule } from '@/api/gateway/quota-rules'

import { matchQuotaRulesForContext, quotaListParamsForContext } from './quota-rule-utils'

function upstreamRule(
  credentialId: string,
  modelName: string | null,
  overrides: Partial<QuotaRule> = {}
): QuotaRule {
  return {
    key: {
      team_id: 'team-1',
      layer: 'upstream',
      user_id: null,
      credential_id: credentialId,
      model_name: modelName,
      period: null,
      window_seconds: 86400,
      reset_strategy: 'rolling',
      access_kind: 'none',
      access_id: null,
      quota_label: 'default',
      target_kind: null,
      target_id: null,
    },
    source_ref: {
      layer: 'upstream',
      budget_id: null,
      plan_id: 'plan-1',
      quota_id: 'quota-1',
    },
    limits: {
      limit_usd: 100,
      soft_limit_usd: null,
      limit_tokens: null,
      limit_requests: null,
      unit_price_usd_per_token: null,
      unit_price_usd_per_request: null,
    },
    usage: null,
    plan_label: 'test-plan',
    is_active: true,
    ...overrides,
  }
}

describe('matchQuotaRulesForContext credential upstream', () => {
  it('filters upstream rules by credential_id', () => {
    const rules = [
      upstreamRule('cred-a', 'gpt-4'),
      upstreamRule('cred-b', 'gpt-4'),
      upstreamRule('cred-a', null),
    ]
    const matched = matchQuotaRulesForContext(rules, {
      kind: 'credential',
      userId: 'u1',
      linkedModelNames: ['gpt-4'],
      credentialId: 'cred-a',
    })
    expect(matched.map((r) => r.key.credential_id)).toEqual(['cred-a', 'cred-a'])
  })

  it('includes whole-credential upstream rules for matching credential', () => {
    const rules = [upstreamRule('cred-a', null), upstreamRule('cred-b', null)]
    const matched = matchQuotaRulesForContext(rules, {
      kind: 'credential',
      userId: 'u1',
      linkedModelNames: ['gpt-4'],
      credentialId: 'cred-a',
    })
    expect(matched).toHaveLength(1)
    expect(matched[0].key.credential_id).toBe('cred-a')
  })
})

describe('quotaListParamsForContext credential', () => {
  it('passes credential_id for server-side narrowing', () => {
    expect(
      quotaListParamsForContext({
        kind: 'credential',
        userId: 'u1',
        linkedModelNames: ['m1'],
        credentialId: 'cred-a',
      })
    ).toEqual({ credential_id: 'cred-a', include_usage: true })
  })
})
