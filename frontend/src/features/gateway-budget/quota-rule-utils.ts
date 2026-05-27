import type { ListQuotaRulesParams, QuotaRule, QuotaRuleLayer } from '@/api/gateway/quota-rules'

import type { BudgetViewContext } from './budget-match'

export const LAYER_LABELS: Record<QuotaRuleLayer, string> = {
  platform: '平台配额',
  upstream: '上游配额',
  downstream: '下游权益',
}

export function quotaRuleRowId(rule: QuotaRule): string {
  const ref = rule.source_ref
  if (ref.budget_id) return `budget:${ref.budget_id}`
  return `plan:${ref.plan_id ?? ''}:${ref.quota_id ?? ''}`
}

export function formatQuotaRulePeriod(rule: QuotaRule): string {
  if (rule.key.period) {
    switch (rule.key.period) {
      case 'daily':
        return '每日'
      case 'monthly':
        return '每月'
      case 'total':
        return '总额'
      default:
        return rule.key.period
    }
  }
  if (rule.key.window_seconds !== null) {
    if (rule.key.window_seconds === 0) return '套餐周期'
    const hours = rule.key.window_seconds / 3600
    if (hours >= 1 && Number.isInteger(hours)) return `${String(hours)}h`
    return `${String(rule.key.window_seconds)}s`
  }
  return '—'
}

export interface QuotaRuleLabelContext {
  memberLabels: Map<string, string>
  keyLabels: Map<string, string>
  credentialLabels: Map<string, string>
}

export function resolveQuotaRuleSubjectLabel(rule: QuotaRule, ctx: QuotaRuleLabelContext): string {
  if (rule.key.layer === 'platform') {
    if (rule.key.target_kind === 'tenant') return '全团队'
    if (rule.key.target_kind === 'system') return '系统'
    if (rule.key.target_kind === 'user' && rule.key.user_id) {
      return ctx.memberLabels.get(rule.key.user_id) ?? rule.key.user_id.slice(0, 8)
    }
    if (rule.key.target_kind === 'key' && rule.key.access_id) {
      return ctx.keyLabels.get(rule.key.access_id) ?? rule.key.access_id.slice(0, 8)
    }
  }
  if (rule.key.access_kind === 'vkey' && rule.key.access_id) {
    return ctx.keyLabels.get(rule.key.access_id) ?? `Key ${rule.key.access_id.slice(0, 8)}`
  }
  if (rule.key.access_kind === 'apikey_grant' && rule.key.access_id) {
    return `Grant ${rule.key.access_id.slice(0, 8)}`
  }
  if (rule.key.user_id) {
    return ctx.memberLabels.get(rule.key.user_id) ?? rule.key.user_id.slice(0, 8)
  }
  return '全团队'
}

export function resolveQuotaRuleCredentialLabel(
  rule: QuotaRule,
  ctx: QuotaRuleLabelContext
): string {
  if (!rule.key.credential_id) return '—'
  return ctx.credentialLabels.get(rule.key.credential_id) ?? rule.key.credential_id.slice(0, 8)
}

/** 按资源上下文过滤可见配额规则（嵌入只读页使用）。 */
export function matchQuotaRulesForContext(rules: QuotaRule[], ctx: BudgetViewContext): QuotaRule[] {
  switch (ctx.kind) {
    case 'personal':
      return rules.filter((r) => {
        if (r.key.layer !== 'platform' || r.key.user_id !== ctx.userId) return false
        const names = ctx.modelNames ?? []
        if (names.length === 0) return r.key.model_name === null
        return r.key.model_name === null || names.includes(r.key.model_name)
      })
    case 'team_model':
      return rules.filter((r) => {
        if (r.key.model_name !== null && r.key.model_name !== ctx.modelName) return false
        if (r.key.layer === 'platform') {
          if (r.key.target_kind === 'tenant') return true
          if (r.key.target_kind === 'user' && ctx.userId && r.key.user_id === ctx.userId) {
            return true
          }
        }
        if (r.key.layer === 'upstream' || r.key.layer === 'downstream') {
          return r.key.model_name === null || r.key.model_name === ctx.modelName
        }
        return false
      })
    case 'credential':
      return rules.filter((r) => {
        if (r.key.layer === 'upstream') {
          return ctx.linkedModelNames.length === 0
            ? true
            : r.key.model_name === null || ctx.linkedModelNames.includes(r.key.model_name)
        }
        if (r.key.layer === 'platform') {
          if (r.key.target_kind === 'tenant') return true
          if (r.key.target_kind === 'user' && r.key.user_id === ctx.userId) return true
        }
        return false
      })
    case 'virtual_key':
      return rules.filter(
        (r) =>
          (r.key.layer === 'platform' &&
            r.key.target_kind === 'key' &&
            r.key.access_id === ctx.keyId) ||
          (r.key.layer === 'downstream' &&
            r.key.access_kind === 'vkey' &&
            r.key.access_id === ctx.keyId)
      )
  }
}

export function computeQuotaRuleUsageRatio(rule: QuotaRule): {
  ratio: number
  barColor: string
} {
  const usage = rule.usage
  const limitUsd = rule.limits.limit_usd
  const limitTok = rule.limits.limit_tokens
  if (!usage || (limitUsd === null && limitTok === null)) {
    return { ratio: 0, barColor: 'bg-muted' }
  }
  const usdRatio = limitUsd !== null && limitUsd > 0 ? usage.current_usd / limitUsd : 0
  const tokRatio = limitTok !== null && limitTok > 0 ? usage.current_tokens / limitTok : 0
  const ratio = Math.max(usdRatio, tokRatio)
  const barColor = ratio >= 1 ? 'bg-destructive' : ratio >= 0.9 ? 'bg-amber-500' : 'bg-emerald-500'
  return { ratio, barColor }
}

/** 嵌入页服务端预过滤，减少全量拉取（client-passive / async-parallel 前置收窄）。 */
export function quotaListParamsForContext(
  context: BudgetViewContext
): ListQuotaRulesParams | undefined {
  switch (context.kind) {
    case 'personal':
      return { user_id: context.userId }
    case 'team_model':
      return { model_name: context.modelName }
    default:
      return undefined
  }
}
