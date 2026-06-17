import { describe, expect, it } from 'vitest'

import type { QuotaRule } from '@/api/gateway/quota-rules'
import { quotaRuleToBatchFormValues } from '@/features/gateway-budget/quota-batch-from-rule'
import {
  buildModelQuotaDefaultForm,
  canCreateUpstreamQuotaOnModelDetail,
  canEditQuotaRuleOnModelDetail,
  isModelDetailEditableQuotaRule,
} from '@/features/gateway-models/detail/model-detail-quota-utils'

function platformRule(overrides: Partial<QuotaRule> = {}): QuotaRule {
  return {
    key: {
      team_id: 'team-1',
      layer: 'platform',
      user_id: null,
      credential_id: null,
      model_name: 'gpt-test',
      period: 'monthly',
      window_seconds: null,
      reset_strategy: null,
      access_kind: 'none',
      access_id: null,
      quota_label: null,
      target_kind: 'tenant',
      target_id: null,
    },
    source_ref: { layer: 'platform', budget_id: 'budget-1', plan_id: null, quota_id: null },
    limits: {
      limit_usd: 100,
      soft_limit_usd: null,
      limit_tokens: null,
      limit_requests: null,
      unit_price_usd_per_token: null,
      unit_price_usd_per_request: null,
    },
    usage: null,
    plan_label: null,
    is_active: true,
    ...overrides,
  }
}

function upstreamRule(overrides: Partial<QuotaRule> = {}): QuotaRule {
  return {
    key: {
      team_id: 'team-1',
      layer: 'upstream',
      user_id: null,
      credential_id: 'cred-1',
      model_name: 'gpt-test',
      period: null,
      window_seconds: 86400,
      reset_strategy: null,
      access_kind: 'none',
      access_id: null,
      quota_label: 'default',
      target_kind: null,
      target_id: null,
    },
    source_ref: { layer: 'upstream', budget_id: 'budget-up-1', plan_id: null, quota_id: null },
    limits: {
      limit_usd: 50,
      soft_limit_usd: null,
      limit_tokens: 1000000,
      limit_requests: null,
      unit_price_usd_per_token: null,
      unit_price_usd_per_request: null,
    },
    usage: null,
    plan_label: null,
    is_active: true,
    ...overrides,
  }
}

describe('isModelDetailEditableQuotaRule', () => {
  it('allows platform and upstream rules with budget_id', () => {
    expect(isModelDetailEditableQuotaRule(platformRule())).toBe(true)
    expect(isModelDetailEditableQuotaRule(upstreamRule())).toBe(true)
  })

  it('allows upstream plan rules with plan_id and quota_id', () => {
    expect(
      isModelDetailEditableQuotaRule(
        upstreamRule({
          source_ref: {
            layer: 'upstream',
            budget_id: null,
            plan_id: 'plan-1',
            quota_id: 'quota-1',
          },
        })
      )
    ).toBe(true)
  })

  it('rejects downstream and rules without writable refs', () => {
    expect(
      isModelDetailEditableQuotaRule(
        platformRule({
          key: { ...platformRule().key, layer: 'downstream' },
          source_ref: { layer: 'downstream', budget_id: 'b1', plan_id: null, quota_id: null },
        })
      )
    ).toBe(false)
    expect(
      isModelDetailEditableQuotaRule(
        platformRule({
          source_ref: { layer: 'platform', budget_id: null, plan_id: 'plan-1', quota_id: null },
        })
      )
    ).toBe(false)
  })
})

describe('canEditQuotaRuleOnModelDetail', () => {
  it('allows admin to edit tenant platform rules', () => {
    expect(canEditQuotaRuleOnModelDetail(platformRule(), { isAdmin: true, userId: 'user-1' })).toBe(
      true
    )
  })

  it('allows member to edit own user platform rules only', () => {
    const ownRule = platformRule({
      key: { ...platformRule().key, target_kind: 'user', user_id: 'user-1' },
    })
    expect(canEditQuotaRuleOnModelDetail(ownRule, { isAdmin: false, userId: 'user-1' })).toBe(true)
    expect(
      canEditQuotaRuleOnModelDetail(platformRule(), { isAdmin: false, userId: 'user-1' })
    ).toBe(false)
  })

  it('allows member upstream edit only on owned credential', () => {
    expect(
      canEditQuotaRuleOnModelDetail(upstreamRule(), {
        isAdmin: false,
        userId: 'user-1',
        credentialOwnerId: 'user-1',
      })
    ).toBe(true)
    expect(
      canEditQuotaRuleOnModelDetail(upstreamRule(), {
        isAdmin: false,
        userId: 'user-1',
        credentialOwnerId: 'user-2',
      })
    ).toBe(false)
  })
})

describe('canCreateUpstreamQuotaOnModelDetail', () => {
  it('requires credential ownership for members', () => {
    expect(
      canCreateUpstreamQuotaOnModelDetail({
        isAdmin: false,
        userId: 'user-1',
        credentialId: 'cred-1',
        credentialOwnerId: 'user-1',
      })
    ).toBe(true)
    expect(
      canCreateUpstreamQuotaOnModelDetail({
        isAdmin: true,
        userId: 'user-1',
        credentialId: 'cred-1',
        credentialOwnerId: 'user-2',
      })
    ).toBe(true)
  })
})

describe('buildModelQuotaDefaultForm', () => {
  it('locks model name for team admin platform quota', () => {
    const form = buildModelQuotaDefaultForm({
      modelName: 'my-model',
      credentialId: 'cred-1',
      layer: 'platform',
    })
    expect(form.allModels).toBe(false)
    expect(form.modelNames).toEqual(['my-model'])
    expect(form.layer).toBe('platform')
    expect(form.subjectMode).toBe('tenant')
  })

  it('pre-fills upstream credential and model', () => {
    const form = buildModelQuotaDefaultForm({
      modelName: 'dashscope/qwen-max',
      credentialId: 'cred-1',
      layer: 'upstream',
    })
    expect(form.layer).toBe('upstream')
    expect(form.credentialIds).toEqual(['cred-1'])
    expect(form.modelNames).toEqual(['dashscope/qwen-max'])
  })

  it('locks member self-service to platform + self user', () => {
    const form = buildModelQuotaDefaultForm({
      modelName: 'qwen-max',
      credentialId: 'cred-1',
      memberMode: true,
      selfUserId: 'user-1',
    })
    expect(form.layer).toBe('platform')
    expect(form.subjectMode).toBe('users')
    expect(form.userIds).toEqual(['user-1'])
    expect(form.credentialIds).toEqual(['cred-1'])
  })
})

describe('quotaRuleToBatchFormValues upstream', () => {
  it('round-trips upstream rules for model detail edit', () => {
    const parsed = quotaRuleToBatchFormValues(upstreamRule())
    expect(parsed).not.toBeNull()
    expect(parsed?.values.layer).toBe('upstream')
    expect(parsed?.values.modelNames).toEqual(['gpt-test'])
    expect(parsed?.values.credentialIds).toEqual(['cred-1'])
    expect(parsed?.values.limit_usd).toBe('50')
    expect(parsed?.values.limit_tokens).toBe('1000000')
    expect(parsed?.values.windowSeconds).toBe('86400')
  })
})
