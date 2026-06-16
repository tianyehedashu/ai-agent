import type { GatewayModel } from '@/api/gateway/models'
import type { PersonalGatewayModel } from '@/api/gateway/my-models'
import type { ListQuotaRulesParams, QuotaRule, QuotaRuleLayer } from '@/api/gateway/quota-rules'
import {
  modelsIndexHref,
  personalModelDetailHref,
  systemModelDetailHref,
  teamModelDetailHref,
  teamModelsFilteredHref,
} from '@/features/gateway-models/paths'

import type { BudgetViewContext } from './budget-match'

export const LAYER_LABELS: Record<QuotaRuleLayer, string> = {
  platform: '平台配额',
  upstream: '上游配额',
  downstream: '下游权益',
}

export const LAYER_ORDER: Record<QuotaRuleLayer, number> = {
  platform: 0,
  upstream: 1,
  downstream: 2,
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

export interface QuotaRuleModelRef {
  modelId: string
  registryKind: 'team' | 'system' | 'personal'
  /** Gateway 调用别名（`gateway_models.name` / personal `name`） */
  aliasName: string
}

export interface QuotaRuleLabelContext {
  memberLabels: Map<string, string>
  keyLabels: Map<string, string>
  credentialLabels: Map<string, string>
  /** upstream 计划配额：`credentialId:realModel` → 模型详情 */
  modelRefByCredentialRealModel?: Map<string, QuotaRuleModelRef>
  /** 全量模型目录加载中（避免链接在 lookup 完成前误降级为列表页） */
  planRuleModelLookupLoading?: boolean
}

/** 是否存在需跳转模型详情的 upstream 计划类规则（``budget_id IS NULL``）。 */
export function hasUpstreamPlanRules(rules: readonly QuotaRule[]): boolean {
  return rules.some((rule) => rule.source_ref.budget_id === null && rule.key.layer === 'upstream')
}

export function quotaRuleCredentialRealModelKey(credentialId: string, realModel: string): string {
  return `${credentialId}:${realModel}`
}

export function buildQuotaRuleModelLookup(
  models: readonly Pick<
    GatewayModel,
    'id' | 'name' | 'credential_id' | 'real_model' | 'registry_kind'
  >[]
): Map<string, QuotaRuleModelRef> {
  const map = new Map<string, QuotaRuleModelRef>()
  for (const model of models) {
    const realModel = model.real_model.trim()
    const aliasName = model.name.trim()
    if (!realModel || !aliasName) continue
    const key = quotaRuleCredentialRealModelKey(model.credential_id, realModel)
    if (map.has(key)) continue
    map.set(key, {
      modelId: model.id,
      registryKind: model.registry_kind === 'system' ? 'system' : 'team',
      aliasName,
    })
  }
  return map
}

/** 合并团队/系统 callable 与个人 BYOK 模型，供 upstream 计划配额深链解析。 */
export function buildQuotaRuleModelLookupFromCatalog(input: {
  teamModels?: readonly Pick<
    GatewayModel,
    'id' | 'name' | 'credential_id' | 'real_model' | 'registry_kind'
  >[]
  personalModels?: readonly Pick<
    PersonalGatewayModel,
    'id' | 'name' | 'display_name' | 'credential_id' | 'model_id'
  >[]
}): Map<string, QuotaRuleModelRef> {
  const map = buildQuotaRuleModelLookup(input.teamModels ?? [])
  for (const model of input.personalModels ?? []) {
    const realModel = model.model_id.trim()
    const aliasName = model.name.trim() || model.display_name.trim()
    if (!realModel || !aliasName) continue
    const key = quotaRuleCredentialRealModelKey(model.credential_id, realModel)
    if (map.has(key)) continue
    map.set(key, { modelId: model.id, registryKind: 'personal', aliasName })
  }
  return map
}

export interface QuotaRulePlanManagementLink {
  href: string
  label: string
}

/** 计划类 upstream/downstream 规则的操作列跳转（upstream → 模型详情/列表）。 */
export function resolveQuotaRulePlanManagementLink(
  rule: QuotaRule,
  ctx: QuotaRuleLabelContext
): QuotaRulePlanManagementLink | null {
  if (rule.key.layer === 'downstream') {
    const id = rule.key.access_id ?? undefined
    return {
      href: `/gateway/virtual-keys${id ? `?id=${id}` : ''}`,
      label: '去 Key 页管理',
    }
  }
  if (rule.key.layer !== 'upstream') return null

  const teamId = rule.key.team_id
  const credentialId = rule.key.credential_id ?? undefined
  const realModel = rule.key.model_name?.trim()

  if (realModel && credentialId && ctx.modelRefByCredentialRealModel) {
    const ref = ctx.modelRefByCredentialRealModel.get(
      quotaRuleCredentialRealModelKey(credentialId, realModel)
    )
    if (ref) {
      const href =
        ref.registryKind === 'personal'
          ? personalModelDetailHref(teamId, ref.modelId)
          : ref.registryKind === 'system'
            ? systemModelDetailHref(teamId, ref.modelId, credentialId)
            : teamModelDetailHref(teamId, ref.modelId, { credentialId })
      return { href, label: '去模型详情管理' }
    }
    if (ctx.planRuleModelLookupLoading) {
      return null
    }
  }

  if (credentialId) {
    return {
      href: teamModelsFilteredHref(teamId, credentialId),
      label: realModel ? '去模型列表' : '查看关联模型',
    }
  }

  return {
    href: modelsIndexHref(teamId),
    label: '去模型列表',
  }
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

/**
 * 配额中心「模型」列：platform 用别名；upstream 用目录解析的 Gateway 别名，
 * 解析不到则回退上游 endpoint（`real_model`）。不用 `plan_label`（那是「来源」列的套餐名）。
 */
export function resolveQuotaRuleModelLabel(rule: QuotaRule, ctx?: QuotaRuleLabelContext): string {
  if (!rule.key.model_name) return '（全模型）'
  if (rule.key.layer === 'upstream') {
    const credentialId = rule.key.credential_id
    const realModel = rule.key.model_name.trim()
    if (credentialId && ctx?.modelRefByCredentialRealModel) {
      const ref = ctx.modelRefByCredentialRealModel.get(
        quotaRuleCredentialRealModelKey(credentialId, realModel)
      )
      if (ref?.aliasName) return ref.aliasName
    }
    return realModel
  }
  return rule.key.model_name
}

/** 按资源上下文过滤可见配额规则（嵌入只读页使用）。 */
export function matchQuotaRulesForContext(rules: QuotaRule[], ctx: BudgetViewContext): QuotaRule[] {
  switch (ctx.kind) {
    case 'personal':
      return rules.filter((r) => {
        if (r.key.layer === 'platform') {
          if (r.key.user_id !== ctx.userId) return false
          const names = ctx.modelNames ?? []
          if (names.length === 0) return r.key.model_name === null
          return r.key.model_name === null || names.includes(r.key.model_name)
        }
        if (r.key.layer === 'upstream') {
          if (
            ctx.credentialId &&
            r.key.credential_id !== null &&
            r.key.credential_id !== ctx.credentialId
          ) {
            return false
          }
          const names = ctx.modelNames ?? []
          if (r.key.model_name === null) return true
          return names.length > 0 && names.includes(r.key.model_name)
        }
        return false
      })
    case 'team_model':
      return rules.filter((r) => {
        if (r.key.layer === 'platform') {
          if (r.key.model_name !== null && r.key.model_name !== ctx.modelName) return false
          if (r.key.target_kind === 'tenant') return true
          if (r.key.target_kind === 'user' && ctx.userId && r.key.user_id === ctx.userId) {
            return true
          }
          return false
        }
        if (r.key.layer === 'upstream') {
          if (
            ctx.credentialId &&
            r.key.credential_id !== null &&
            r.key.credential_id !== ctx.credentialId
          ) {
            return false
          }
          if (r.key.model_name === null) return true
          const realModel = ctx.realModel?.trim()
          return Boolean(realModel) && r.key.model_name === realModel
        }
        return r.key.model_name === null || r.key.model_name === ctx.modelName
      })
    case 'credential':
      return rules.filter((r) => {
        if (r.key.layer === 'upstream') {
          if (
            ctx.credentialId !== undefined &&
            r.key.credential_id !== null &&
            r.key.credential_id !== ctx.credentialId
          ) {
            return false
          }
          return ctx.linkedModelNames.length === 0
            ? true
            : r.key.model_name === null || ctx.linkedModelNames.includes(r.key.model_name)
        }
        if (r.key.layer === 'platform') {
          if (r.key.target_kind === 'tenant') return true
          if (r.key.target_kind === 'user' && r.key.user_id === ctx.userId) {
            // 成员规则仅展示与本凭据相关或无凭据维度的行，避免串显其它凭据限额。
            return (
              r.key.credential_id === null ||
              ctx.credentialId === undefined ||
              r.key.credential_id === ctx.credentialId
            )
          }
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

export interface StatsQuotaLookup {
  /** Gateway 调用别名 → 上游 endpoint 绑定 */
  aliasToUpstream: ReadonlyMap<string, { credentialId: string; realModel: string }>
}

/** 由 callable 模型目录构建统计页 upstream 配额匹配索引。 */
export function buildStatsQuotaLookup(
  models: readonly { name: string; credential_id: string; real_model: string }[]
): StatsQuotaLookup {
  const aliasToUpstream = new Map<string, { credentialId: string; realModel: string }>()
  for (const model of models) {
    const alias = model.name.trim()
    const realModel = model.real_model.trim()
    if (!alias || !realModel) continue
    if (!aliasToUpstream.has(alias)) {
      aliasToUpstream.set(alias, { credentialId: model.credential_id, realModel })
    }
  }
  return { aliasToUpstream }
}

function findUpstreamQuotaForStatsRow(
  upstream: readonly QuotaRule[],
  credentialId: string,
  realModel: string | null
): QuotaRule | null {
  return (
    upstream.find(
      (r) =>
        r.key.credential_id === credentialId && realModel !== null && r.key.model_name === realModel
    ) ??
    upstream.find((r) => r.key.credential_id === credentialId && r.key.model_name === null) ??
    null
  )
}

/**
 * 调用统计行 → 对应配额规则（best-effort）。
 *
 * 优先 platform；未命中时按模型目录解析 upstream（别名 → real_model）。
 */
export function findQuotaRuleForStatsRow(
  rules: readonly QuotaRule[],
  groupBy: string,
  row: { group_key: string; group_key_parts?: string[] | null },
  lookup?: StatsQuotaLookup
): QuotaRule | null {
  const platform = rules.filter((r) => r.key.layer === 'platform')
  const upstream = rules.filter((r) => r.key.layer === 'upstream')
  if (groupBy === 'user') {
    const matched =
      platform.find(
        (r) =>
          r.key.target_kind === 'user' &&
          r.key.user_id === row.group_key &&
          r.key.credential_id === null &&
          r.key.model_name === null
      ) ?? null
    return matched
  }
  if (groupBy === 'credential') {
    return (
      platform.find((r) => r.key.credential_id === row.group_key) ??
      findUpstreamQuotaForStatsRow(upstream, row.group_key, null)
    )
  }
  if (groupBy === 'model') {
    const platformMatch =
      platform.find((r) => r.key.model_name === row.group_key && r.key.target_kind === 'tenant') ??
      platform.find((r) => r.key.model_name === row.group_key) ??
      null
    if (platformMatch) return platformMatch
    const resolved = lookup?.aliasToUpstream.get(row.group_key)
    if (!resolved) return null
    return findUpstreamQuotaForStatsRow(upstream, resolved.credentialId, resolved.realModel)
  }
  if (groupBy === 'user_model_credential') {
    const parts = row.group_key_parts ?? []
    const [userId, model, credId] = parts
    if (!userId || !credId) return null
    const platformMatch =
      platform.find(
        (r) =>
          r.key.target_kind === 'user' &&
          r.key.user_id === userId &&
          r.key.credential_id === credId &&
          (r.key.model_name === model || r.key.model_name === null)
      ) ?? null
    if (platformMatch) return platformMatch
    const resolved = model ? lookup?.aliasToUpstream.get(model) : undefined
    const realModel = resolved?.realModel ?? (model || null)
    return findUpstreamQuotaForStatsRow(upstream, credId, realModel)
  }
  return null
}

/** API 用量/限额字段可能是 number 或 numeric string，统一解析为有限数值。 */
export function parseQuotaNumeric(value: unknown): number {
  const parsed = Number.parseFloat(String(value))
  return Number.isFinite(parsed) ? parsed : 0
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
  const usdRatio =
    limitUsd !== null && limitUsd > 0
      ? parseQuotaNumeric(usage.current_usd) / parseQuotaNumeric(limitUsd)
      : 0
  const tokRatio =
    limitTok !== null && limitTok > 0
      ? parseQuotaNumeric(usage.current_tokens) / parseQuotaNumeric(limitTok)
      : 0
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
      return { user_id: context.userId, include_usage: true }
    case 'team_model':
      return { model_name: context.modelName, include_usage: true }
    case 'credential':
      return {
        credential_id: context.credentialId,
        include_usage: true,
      }
    case 'virtual_key':
      return { include_usage: true }
  }
}

/** 模型详情页：platform 规则按注册别名预过滤。 */
export function quotaListParamsForTeamModelPlatform(modelName: string): ListQuotaRulesParams {
  return { model_name: modelName, include_usage: true }
}

/** 模型详情页：upstream 规则按凭据 + real_model 预过滤（含凭据级 model_name=null 规则）。 */
export function quotaListParamsForTeamModelUpstream(
  credentialId: string,
  realModel: string
): ListQuotaRulesParams {
  return {
    layer: 'upstream',
    credential_id: credentialId,
    model_name: realModel,
    include_usage: true,
  }
}

/** 合并多次 quota-rules 请求结果并去重。 */
export function mergeQuotaRules(
  ...groups: readonly (readonly QuotaRule[] | undefined)[]
): QuotaRule[] {
  const seen = new Set<string>()
  const merged: QuotaRule[] = []
  for (const group of groups) {
    for (const rule of group ?? []) {
      const id = quotaRuleRowId(rule)
      if (seen.has(id)) continue
      seen.add(id)
      merged.push(rule)
    }
  }
  return merged
}

/** upstream 规则在模型详情中的适用范围文案。 */
export function describeUpstreamQuotaRuleScope(rule: QuotaRule, currentRealModel?: string): string {
  if (rule.key.layer !== 'upstream') return ''
  const endpoint = rule.key.model_name?.trim()
  if (!endpoint) return '整凭据'
  if (currentRealModel?.trim() === endpoint) return '本 endpoint'
  return endpoint
}
