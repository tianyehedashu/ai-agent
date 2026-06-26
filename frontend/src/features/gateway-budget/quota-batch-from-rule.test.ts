import { describe, expect, it } from 'vitest'

import type { QuotaRule } from '@/api/gateway/quota-rules'

import { quotaRuleToBatchFormValues, quotaRuleToScopePrefill } from './quota-batch-from-rule'

function downstreamVkeyRule(overrides: Partial<QuotaRule> = {}): QuotaRule {
  return {
    key: {
      team_id: 'team-1',
      layer: 'downstream',
      user_id: null,
      credential_id: null,
      model_name: 'gpt-4',
      period: null,
      window_seconds: 86400,
      reset_strategy: 'calendar_daily_utc',
      period_timezone: 'UTC',
      period_reset_minutes: 0,
      period_reset_day: 1,
      access_kind: 'vkey',
      access_id: 'vkey-1',
      quota_label: 'default',
      target_kind: null,
      target_id: null,
    },
    source_ref: {
      layer: 'downstream',
      budget_id: null,
      plan_id: 'plan-1',
      quota_id: 'quota-1',
    },
    limits: {
      limit_usd: 50,
      soft_limit_usd: null,
      limit_tokens: 1000,
      limit_requests: null,
      limit_images: null,
      unit_price_usd_per_token: null,
      unit_price_usd_per_request: null,
    },
    usage: null,
    is_active: true,
    valid_from: '2026-01-01T00:00:00.000Z',
    valid_until: null,
    ...overrides,
  }
}

describe('quotaRuleToBatchFormValues downstream', () => {
  it('maps vkey downstream rule to batch form', () => {
    const parsed = quotaRuleToBatchFormValues(downstreamVkeyRule())
    expect(parsed).not.toBeNull()
    expect(parsed?.values.layer).toBe('downstream')
    expect(parsed?.values.keyIds).toEqual(['vkey-1'])
    expect(parsed?.values.quotaLabel).toBe('default')
    expect(parsed?.values.windowSeconds).toBe('86400')
    expect(parsed?.values.modelNames).toEqual(['gpt-4'])
    expect(parsed?.values.limit_usd).toBe('50')
    expect(parsed?.values.limit_tokens).toBe('1000')
    expect(parsed?.info.originalTargetId).toBe('vkey-1')
  })

  it('maps limit_images to batch form for image-capable rule', () => {
    const parsed = quotaRuleToBatchFormValues(
      downstreamVkeyRule({
        limits: {
          limit_usd: null,
          soft_limit_usd: null,
          limit_tokens: null,
          limit_requests: null,
          limit_images: 50,
          unit_price_usd_per_token: null,
          unit_price_usd_per_request: null,
        },
      })
    )
    expect(parsed).not.toBeNull()
    expect(parsed?.values.limit_images).toBe('50')
    // 其它限额字段应为空
    expect(parsed?.values.limit_usd).toBe('')
    expect(parsed?.values.limit_tokens).toBe('')
    expect(parsed?.values.limit_requests).toBe('')
  })

  it('returns null for apikey_grant downstream', () => {
    const rule = downstreamVkeyRule({
      key: {
        ...downstreamVkeyRule().key,
        access_kind: 'apikey_grant',
        access_id: 'grant-1',
      },
    })
    expect(quotaRuleToBatchFormValues(rule)).toBeNull()
  })

  it('returns null when quota_id missing', () => {
    const rule = downstreamVkeyRule({
      source_ref: {
        layer: 'downstream',
        budget_id: null,
        plan_id: 'plan-1',
        quota_id: null,
      },
    })
    expect(quotaRuleToBatchFormValues(rule)).toBeNull()
  })
})

describe('quotaRuleToScopePrefill', () => {
  it('clears limits and validity for copy-add', () => {
    const prefill = quotaRuleToScopePrefill(downstreamVkeyRule())
    expect(prefill).not.toBeNull()
    expect(prefill?.limit_usd).toBe('')
    expect(prefill?.limit_tokens).toBe('')
    expect(prefill?.limit_requests).toBe('')
    expect(prefill?.limit_images).toBe('')
    expect(prefill?.validFrom).toBe('')
    expect(prefill?.validUntil).toBe('')
    expect(prefill?.keyIds).toEqual(['vkey-1'])
  })

  it('clears limit_images even when rule has images quota set', () => {
    const prefill = quotaRuleToScopePrefill(
      downstreamVkeyRule({
        limits: {
          limit_usd: null,
          soft_limit_usd: null,
          limit_tokens: null,
          limit_requests: null,
          limit_images: 100,
          unit_price_usd_per_token: null,
          unit_price_usd_per_request: null,
        },
      })
    )
    expect(prefill).not.toBeNull()
    expect(prefill?.limit_images).toBe('')
  })

  it('dedupes quota label for upstream/downstream copy', () => {
    const upstreamRule: QuotaRule = {
      ...downstreamVkeyRule(),
      key: {
        ...downstreamVkeyRule().key,
        layer: 'upstream',
        access_kind: 'none',
        access_id: null,
        credential_id: 'cred-1',
        quota_label: 'default',
      },
      source_ref: {
        layer: 'upstream',
        budget_id: null,
        plan_id: null,
        quota_id: 'q-up',
      },
    }
    const prefill = quotaRuleToScopePrefill(upstreamRule)
    expect(prefill?.quotaLabel).toBe('default-copy')
  })
})
