import { describe, expect, it } from 'vitest'

import type { QuotaRule } from '@/api/gateway/quota-rules'

import {
  buildQuotaRuleModelLookupFromCatalog,
  buildStatsQuotaLookup,
  describeUpstreamQuotaRuleScope,
  findQuotaRuleForStatsRow,
  hasUpstreamPlanRules,
  matchQuotaRulesForContext,
  mergeQuotaRules,
  quotaListParamsForContext,
  quotaListParamsForTeamModelPlatform,
  quotaListParamsForTeamModelUpstream,
  quotaRuleCredentialRealModelKey,
  resolveQuotaRuleModelLabel,
  resolveQuotaRulePlanManagementLink,
  type QuotaRuleLabelContext,
} from './quota-rule-utils'

function tokenLimits(tokens: number): QuotaRule['limits'] {
  return {
    limit_usd: null,
    soft_limit_usd: null,
    limit_tokens: tokens,
    limit_requests: null,
    unit_price_usd_per_token: null,
    unit_price_usd_per_request: null,
  }
}

function platformRule(modelName: string, overrides: Partial<QuotaRule> = {}): QuotaRule {
  return {
    key: {
      team_id: 'team-1',
      layer: 'platform',
      user_id: null,
      credential_id: 'cred-a',
      model_name: modelName,
      period: 'monthly',
      window_seconds: null,
      reset_strategy: null,
      access_kind: 'none',
      access_id: null,
      quota_label: null,
      target_kind: 'tenant',
      target_id: null,
    },
    source_ref: {
      layer: 'platform',
      budget_id: 'b1',
      plan_id: null,
      quota_id: null,
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
    plan_label: null,
    is_active: true,
    ...overrides,
  }
}

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

describe('matchQuotaRulesForContext team_model', () => {
  it('matches platform by alias and upstream by real_model', () => {
    const rules = [
      upstreamRule('cred-a', 'ep-abc', { limits: tokenLimits(4_000_000) }),
      upstreamRule('cred-a', null, { limits: tokenLimits(1_000_000) }),
      platformRule('Doubao-Seed-Code-online'),
    ]
    const matched = matchQuotaRulesForContext(rules, {
      kind: 'team_model',
      modelName: 'Doubao-Seed-Code-online',
      realModel: 'ep-abc',
      credentialId: 'cred-a',
      userId: 'u1',
    })
    expect(matched.map((r) => [r.key.layer, r.key.model_name, r.limits.limit_tokens])).toEqual([
      ['upstream', 'ep-abc', 4_000_000],
      ['upstream', null, 1_000_000],
      ['platform', 'Doubao-Seed-Code-online', null],
    ])
  })

  it('excludes upstream rules for other real_model endpoints', () => {
    const rules = [upstreamRule('cred-a', 'ep-other')]
    const matched = matchQuotaRulesForContext(rules, {
      kind: 'team_model',
      modelName: 'Doubao-Seed-Code-online',
      realModel: 'ep-abc',
      credentialId: 'cred-a',
    })
    expect(matched).toHaveLength(0)
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

describe('resolveQuotaRulePlanManagementLink', () => {
  const ctx = {
    memberLabels: new Map<string, string>(),
    keyLabels: new Map<string, string>(),
    credentialLabels: new Map<string, string>(),
    modelRefByCredentialRealModel: buildQuotaRuleModelLookupFromCatalog({
      teamModels: [
        {
          id: 'model-1',
          name: 'alias-abc',
          credential_id: 'cred-a',
          real_model: 'ep-abc',
          registry_kind: 'team',
        },
        {
          id: 'sys-1',
          name: 'alias-sys',
          credential_id: 'cred-a',
          real_model: 'ep-sys',
          registry_kind: 'system',
        },
      ],
      personalModels: [
        {
          id: 'pm-1',
          name: 'personal-alias',
          display_name: 'Personal',
          credential_id: 'cred-byok',
          model_id: 'ep-personal',
        },
      ],
    }),
  }

  it('links upstream plan rule to model detail when real_model matches', () => {
    const link = resolveQuotaRulePlanManagementLink(upstreamRule('cred-a', 'ep-abc'), ctx)
    expect(link).toEqual({
      href: '/gateway/teams/team-1/models/model-1?tab=shared&credentialId=cred-a',
      label: '去模型详情管理',
    })
  })

  it('links system registry model to system detail href', () => {
    const link = resolveQuotaRulePlanManagementLink(upstreamRule('cred-a', 'ep-sys'), ctx)
    expect(link).toEqual({
      href: '/gateway/teams/team-1/models/sys-1?tab=system&credentialId=cred-a',
      label: '去模型详情管理',
    })
  })

  it('links personal BYOK model to personal detail href', () => {
    const link = resolveQuotaRulePlanManagementLink(upstreamRule('cred-byok', 'ep-personal'), ctx)
    expect(link).toEqual({
      href: '/gateway/teams/team-1/models/pm-1?tab=personal',
      label: '去模型详情管理',
    })
  })

  it('returns null while model lookup is loading and model not yet resolved', () => {
    const link = resolveQuotaRulePlanManagementLink(upstreamRule('cred-a', 'ep-missing'), {
      ...ctx,
      planRuleModelLookupLoading: true,
    })
    expect(link).toBeNull()
  })

  it('falls back to credential-filtered model list when model not in lookup', () => {
    const link = resolveQuotaRulePlanManagementLink(upstreamRule('cred-a', 'ep-missing'), ctx)
    expect(link).toEqual({
      href: '/gateway/teams/team-1/models?credentialId=cred-a&scope=team',
      label: '去模型列表',
    })
  })

  it('links whole-credential upstream rule to filtered model list', () => {
    const link = resolveQuotaRulePlanManagementLink(upstreamRule('cred-a', null), ctx)
    expect(link).toEqual({
      href: '/gateway/teams/team-1/models?credentialId=cred-a&scope=team',
      label: '查看关联模型',
    })
  })

  it('links downstream plan rule to virtual key page', () => {
    const rule: QuotaRule = {
      ...upstreamRule('cred-a', null),
      key: {
        ...upstreamRule('cred-a', null).key,
        layer: 'downstream',
        access_kind: 'vkey',
        access_id: 'vkey-1',
        credential_id: null,
      },
      source_ref: { layer: 'downstream', budget_id: null, plan_id: 'p1', quota_id: 'q1' },
    }
    expect(resolveQuotaRulePlanManagementLink(rule, ctx)).toEqual({
      href: '/gateway/virtual-keys?id=vkey-1',
      label: '去 Key 页管理',
    })
  })
})

describe('quotaRuleCredentialRealModelKey', () => {
  it('joins credential and real model', () => {
    expect(quotaRuleCredentialRealModelKey('cred-a', 'ep-1')).toBe('cred-a:ep-1')
  })
})

describe('hasUpstreamPlanRules', () => {
  it('detects upstream plan rules only', () => {
    expect(hasUpstreamPlanRules([upstreamRule('cred-a', 'm1')])).toBe(true)
    expect(
      hasUpstreamPlanRules([
        {
          ...upstreamRule('cred-a', 'm1'),
          source_ref: { layer: 'upstream', budget_id: 'b1', plan_id: null, quota_id: null },
        },
      ])
    ).toBe(false)
  })
})

describe('buildQuotaRuleModelLookupFromCatalog', () => {
  it('merges team and personal models without overwriting team entries', () => {
    const map = buildQuotaRuleModelLookupFromCatalog({
      teamModels: [
        {
          id: 'team-1',
          name: 'Doubao-team',
          credential_id: 'cred-a',
          real_model: 'ep-x',
          registry_kind: 'team',
        },
      ],
      personalModels: [
        {
          id: 'p-1',
          name: 'p-name',
          display_name: 'Personal',
          credential_id: 'cred-b',
          model_id: 'ep-y',
        },
        {
          id: 'p-2',
          name: 'dup',
          display_name: 'Dup',
          credential_id: 'cred-a',
          model_id: 'ep-x',
        },
      ],
    })
    expect(map.get('cred-a:ep-x')).toEqual({
      modelId: 'team-1',
      registryKind: 'team',
      aliasName: 'Doubao-team',
    })
    expect(map.get('cred-b:ep-y')?.registryKind).toBe('personal')
  })
})

describe('quotaListParamsForTeamModelPlatform', () => {
  it('filters platform rules by alias', () => {
    expect(quotaListParamsForTeamModelPlatform('Doubao-online')).toEqual({
      model_name: 'Doubao-online',
      include_usage: true,
    })
  })
})

describe('quotaListParamsForTeamModelUpstream', () => {
  it('filters upstream by credential and real_model', () => {
    expect(quotaListParamsForTeamModelUpstream('cred-a', 'ep-abc')).toEqual({
      layer: 'upstream',
      credential_id: 'cred-a',
      model_name: 'ep-abc',
      include_usage: true,
    })
  })
})

describe('mergeQuotaRules', () => {
  it('deduplicates rules by row id', () => {
    const rule = upstreamRule('cred-a', 'ep-1')
    expect(mergeQuotaRules([rule], [rule], undefined)).toEqual([rule])
  })

  it('concatenates distinct rules', () => {
    const a = upstreamRule('cred-a', 'ep-1', {
      source_ref: { layer: 'upstream', budget_id: null, plan_id: 'p1', quota_id: 'q1' },
    })
    const b = upstreamRule('cred-a', 'ep-2', {
      source_ref: { layer: 'upstream', budget_id: null, plan_id: 'p1', quota_id: 'q2' },
    })
    expect(mergeQuotaRules([a], [b]).map((r) => r.key.model_name)).toEqual(['ep-1', 'ep-2'])
  })
})

describe('findQuotaRuleForStatsRow upstream', () => {
  const lookup = buildStatsQuotaLookup([
    {
      name: 'Doubao-online',
      credential_id: 'cred-a',
      real_model: 'ep-doubao',
    },
  ])

  it('falls back to upstream when platform model rule missing', () => {
    const upstream = upstreamRule('cred-a', 'ep-doubao')
    const rules = [upstream]
    expect(findQuotaRuleForStatsRow(rules, 'model', { group_key: 'Doubao-online' }, lookup)).toBe(
      upstream
    )
  })

  it('prefers platform over upstream for same alias', () => {
    const platform = platformRule('Doubao-online')
    const upstream = upstreamRule('cred-a', 'ep-doubao')
    expect(
      findQuotaRuleForStatsRow(
        [platform, upstream],
        'model',
        { group_key: 'Doubao-online' },
        lookup
      )
    ).toBe(platform)
  })
})

describe('resolveQuotaRuleModelLabel', () => {
  it('resolves upstream alias from catalog, not plan_label', () => {
    const ctx: QuotaRuleLabelContext = {
      memberLabels: new Map(),
      keyLabels: new Map(),
      credentialLabels: new Map(),
      modelRefByCredentialRealModel: buildQuotaRuleModelLookupFromCatalog({
        teamModels: [
          {
            id: 'm1',
            name: 'daily-4M-Doubao-online',
            credential_id: 'cred-a',
            real_model: 'ep-abc',
            registry_kind: 'team',
          },
        ],
      }),
    }
    expect(
      resolveQuotaRuleModelLabel(
        {
          ...upstreamRule('cred-a', 'ep-abc'),
          plan_label: 'auto-plan-name',
        },
        ctx
      )
    ).toBe('daily-4M-Doubao-online')
  })

  it('falls back to upstream endpoint when catalog miss', () => {
    expect(resolveQuotaRuleModelLabel(upstreamRule('cred-a', 'ep-abc'))).toBe('ep-abc')
  })

  it('uses model_name for platform rules', () => {
    expect(
      resolveQuotaRuleModelLabel({
        ...upstreamRule('cred-a', 'ep-abc'),
        key: {
          ...upstreamRule('cred-a', 'ep-abc').key,
          layer: 'platform',
          model_name: 'my-alias',
        },
      })
    ).toBe('my-alias')
  })
})

describe('describeUpstreamQuotaRuleScope', () => {
  it('labels credential-wide and endpoint scopes', () => {
    expect(describeUpstreamQuotaRuleScope(upstreamRule('cred-a', null))).toBe('整凭据')
    expect(describeUpstreamQuotaRuleScope(upstreamRule('cred-a', 'ep-abc'), 'ep-abc')).toBe(
      '本 endpoint'
    )
    expect(describeUpstreamQuotaRuleScope(upstreamRule('cred-a', 'ep-other'), 'ep-abc')).toBe(
      'ep-other'
    )
  })
})

describe('matchQuotaRulesForContext personal upstream', () => {
  it('includes upstream rules for BYOK real_model', () => {
    const rules = [
      upstreamRule('cred-byok', 'ep-personal', { limits: tokenLimits(4_000_000) }),
      upstreamRule('cred-other', 'ep-x'),
    ]
    const matched = matchQuotaRulesForContext(rules, {
      kind: 'personal',
      userId: 'u1',
      modelNames: ['ep-personal'],
      credentialId: 'cred-byok',
    })
    expect(matched).toHaveLength(1)
    expect(matched[0].limits.limit_tokens).toBe(4_000_000)
  })
})
