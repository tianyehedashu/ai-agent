import type { GatewayModel } from '@/api/gateway/models'
import type { PersonalGatewayModel } from '@/api/gateway/my-models'
import {
  quotaRuleLegacyPlanLabel,
  type ListQuotaRulesParams,
  type QuotaRule,
  type QuotaRuleLayer,
  type QuotaRuleUsage,
} from '@/api/gateway/quota-rules'
import {
  modelsIndexHref,
  personalModelDetailHref,
  systemModelDetailHref,
  teamModelDetailHref,
  teamModelsFilteredHref,
} from '@/features/gateway-models/paths'
import { resolveTeamLabelFromMap } from '@/features/gateway-teams/gateway-team-resolve-label'

import { formatPeriodResetLabel, isCalendarPeriodResetVisible } from './period-reset-utils'
import { quotaRuleToBatchFormValues } from './quota-batch-from-rule'

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
  if (ref.quota_id) return `quota:${ref.quota_id}`
  return `orphan:${rule.key.layer}`
}

export function formatQuotaRulePeriod(rule: QuotaRule): string {
  if (rule.key.period) {
    if (rule.key.period === 'total') return '总额'
    if (rule.key.period === 'daily' || rule.key.period === 'monthly') {
      return formatPeriodResetLabel(
        {
          period_timezone: rule.key.period_timezone,
          period_reset_minutes: rule.key.period_reset_minutes,
          period_reset_day: rule.key.period_reset_day,
        },
        rule.key.period
      )
    }
    return rule.key.period
  }
  if (rule.key.window_seconds !== null) {
    if (rule.key.window_seconds === 0) return '套餐周期'
    if (rule.key.reset_strategy === 'rolling' && rule.key.window_seconds === 86400) {
      return '滚动 24h'
    }
    if (
      isCalendarPeriodResetVisible({
        layer: rule.key.layer,
        windowSeconds: String(rule.key.window_seconds),
        resetStrategy: rule.key.reset_strategy,
      })
    ) {
      const period =
        rule.key.window_seconds === 2592000 || rule.key.reset_strategy === 'calendar_monthly_utc'
          ? 'monthly'
          : 'daily'
      return formatPeriodResetLabel(
        {
          period_timezone: rule.key.period_timezone,
          period_reset_minutes: rule.key.period_reset_minutes,
          period_reset_day: rule.key.period_reset_day,
        },
        period
      )
    }
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
  /** team_id → 团队名称，用于团队级规则主体如实展示其归属团队 */
  teamNameById?: ReadonlyMap<string, string>
  /** upstream 配额：`credentialId:realModel` → 模型详情 */
  modelRefByCredentialRealModel?: Map<string, QuotaRuleModelRef>
  /** 全量模型目录加载中（避免链接在 lookup 完成前误降级为列表页） */
  quotaModelLookupLoading?: boolean
  /** @deprecated 使用 quotaModelLookupLoading */
  planRuleModelLookupLoading?: boolean
}

/** 是否存在需跳转模型详情的 upstream 配额规则。 */
export function hasUpstreamQuotaRules(rules: readonly QuotaRule[]): boolean {
  return rules.some((rule) => rule.key.layer === 'upstream' && rule.source_ref.quota_id !== null)
}

/** @deprecated 使用 hasUpstreamQuotaRules */
export const hasUpstreamPlanRules = hasUpstreamQuotaRules

/** 配额列表是否需要 Gateway 模型目录（解析调用名 / 模型详情深链）。 */
export function needsQuotaModelIdentityLookup(rules: readonly QuotaRule[]): boolean {
  return rules.some((rule) => {
    const modelName = rule.key.model_name?.trim() ?? ''
    if (!modelName) return false
    return rule.key.layer === 'platform' || rule.key.layer === 'upstream'
  })
}

/** 从 cred+real_model 索引提取 ``credentialId:realModel`` → 调用名（用于上游标签/下拉）。 */
export function buildAliasByRealModelFromLookup(
  lookup: ReadonlyMap<string, QuotaRuleModelRef> | undefined
): Map<string, string> {
  const map = new Map<string, string>()
  if (!lookup) return map
  for (const [key, ref] of lookup) {
    if (!key || map.has(key)) continue
    map.set(key, ref.aliasName)
  }
  return map
}

export function resolveQuotaModelAlias(
  credentialId: string | undefined,
  realModel: string,
  aliasByCredentialRealModel: ReadonlyMap<string, string> | undefined
): string | undefined {
  const trimmed = realModel.trim()
  if (!trimmed || !aliasByCredentialRealModel) return undefined
  if (credentialId) {
    const scoped = aliasByCredentialRealModel.get(
      quotaRuleCredentialRealModelKey(credentialId, trimmed)
    )
    if (scoped) return scoped
  }
  for (const [key, alias] of aliasByCredentialRealModel) {
    const colon = key.indexOf(':')
    if (colon >= 0 && key.slice(colon + 1) === trimmed) return alias
  }
  return undefined
}

export function resolveInvokeNameForCredentialRealModel(
  credentialId: string | null | undefined,
  realModel: string,
  lookup: ReadonlyMap<string, QuotaRuleModelRef> | undefined
): string | null {
  const trimmed = realModel.trim()
  if (!trimmed || !credentialId || !lookup) return null
  const ref = lookup.get(quotaRuleCredentialRealModelKey(credentialId, trimmed))
  return ref?.aliasName ?? null
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

/** upstream/downstream 规则的操作列跳转（upstream → 模型详情/列表）。 */
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
    if (ctx.quotaModelLookupLoading) {
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

/** 是否应在模型详情页管理配额（有明确模型绑定）。 */
export function shouldManageQuotaOnModelDetail(rule: QuotaRule): boolean {
  const modelName = rule.key.model_name?.trim() ?? ''
  if (!modelName) return false
  return rule.key.layer === 'platform' || rule.key.layer === 'upstream'
}

export interface CanAddFromRuleOptions {
  mode: 'admin' | 'member'
  selfUserId?: string | null
  /** 成员自助可写凭据（platform 团队凭据 + upstream 个人 BYOK） */
  selfCredentialIds?: ReadonlySet<string>
}

/** 是否可从当前行「复制为新配额」：需可反解且符合成员/admin 写权限边界。 */
export function canAddFromRule(rule: QuotaRule, options: CanAddFromRuleOptions): boolean {
  if (quotaRuleToBatchFormValues(rule) === null) return false
  if (options.mode === 'admin') return true

  const userId = options.selfUserId
  if (!userId) return false

  const layer = rule.key.layer
  if (layer === 'downstream') return false

  if (layer === 'platform') {
    if (rule.key.target_kind !== 'user' || rule.key.user_id !== userId) return false
    const credId = rule.key.credential_id
    if (credId && options.selfCredentialIds && !options.selfCredentialIds.has(credId)) {
      return false
    }
    return true
  }

  const credId = rule.key.credential_id
  if (!credId) return false
  return options.selfCredentialIds?.has(credId) ?? false
}

/** 模型级 platform / upstream 规则 → 模型详情深链（限额与用量在详情页维护）。 */
export function resolveQuotaRuleModelDetailHref(
  rule: QuotaRule,
  ctx: QuotaRuleLabelContext
): string | null {
  if (!shouldManageQuotaOnModelDetail(rule)) return null

  const teamId = rule.key.team_id
  const credentialId = rule.key.credential_id ?? undefined
  const map = ctx.modelRefByCredentialRealModel

  if (rule.key.layer === 'upstream' && credentialId && rule.key.model_name) {
    const realModel = rule.key.model_name.trim()
    const ref = map?.get(quotaRuleCredentialRealModelKey(credentialId, realModel))
    if (ref) {
      return ref.registryKind === 'personal'
        ? personalModelDetailHref(teamId, ref.modelId)
        : ref.registryKind === 'system'
          ? systemModelDetailHref(teamId, ref.modelId, credentialId)
          : teamModelDetailHref(teamId, ref.modelId, { credentialId })
    }
    if (ctx.quotaModelLookupLoading) return null
    return teamModelsFilteredHref(teamId, credentialId)
  }

  if (rule.key.layer === 'platform' && rule.key.model_name) {
    const alias = rule.key.model_name.trim()
    if (map) {
      for (const [key, ref] of map) {
        if (ref.aliasName !== alias) continue
        const colon = key.indexOf(':')
        if (colon < 0) continue
        const credFromKey = key.slice(0, colon)
        if (credentialId && credFromKey !== credentialId) continue
        const cid = credentialId ?? credFromKey
        return ref.registryKind === 'personal'
          ? personalModelDetailHref(teamId, ref.modelId)
          : ref.registryKind === 'system'
            ? systemModelDetailHref(teamId, ref.modelId, cid)
            : teamModelDetailHref(teamId, ref.modelId, { credentialId: cid })
      }
    }
    if (ctx.quotaModelLookupLoading) return null
  }

  return null
}

/** 团队级规则主体：如实显示规则归属团队（rule.key.team_id），目录缺失则降级 ID 前缀。 */
function resolveQuotaRuleTeamLabel(rule: QuotaRule, ctx: QuotaRuleLabelContext): string {
  const teamId = rule.key.team_id
  if (!ctx.teamNameById) return teamId ? `${teamId.slice(0, 8)}…` : '—'
  return resolveTeamLabelFromMap(ctx.teamNameById, teamId)
}

/** 上游配额无主体维度（按凭据 + real_model 全局共享），展示读统一返回占位。 */
export function isQuotaRuleSubjectApplicable(rule: QuotaRule): boolean {
  return rule.key.layer !== 'upstream'
}

export function resolveQuotaRuleSubjectLabel(rule: QuotaRule, ctx: QuotaRuleLabelContext): string {
  if (rule.key.layer === 'upstream') {
    return '—'
  }
  if (rule.key.layer === 'platform') {
    if (rule.key.target_kind === 'tenant') return resolveQuotaRuleTeamLabel(rule, ctx)
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
  return resolveQuotaRuleTeamLabel(rule, ctx)
}

export function resolveQuotaRuleCredentialLabel(
  rule: QuotaRule,
  ctx: QuotaRuleLabelContext
): string {
  if (!rule.key.credential_id) return '—'
  return ctx.credentialLabels.get(rule.key.credential_id) ?? rule.key.credential_id.slice(0, 8)
}

/**
 * 配额规则模型身份（与模型列表 / 调用日志「调用名 · 上游」语义对齐）。
 */
export interface QuotaRuleModelIdentity {
  /** Gateway 注册别名 / platform 的 model_name */
  invokeName: string | null
  /** 上游 real_model / endpoint */
  upstreamName: string | null
}

function findUpstreamNameForInvokeAlias(
  alias: string,
  credentialId: string | null,
  ctx?: QuotaRuleLabelContext
): string | null {
  if (!ctx?.modelRefByCredentialRealModel) return null
  const trimmedAlias = alias.trim()
  if (!trimmedAlias) return null
  for (const [key, ref] of ctx.modelRefByCredentialRealModel) {
    if (ref.aliasName !== trimmedAlias) continue
    if (credentialId) {
      const colon = key.indexOf(':')
      if (colon < 0 || key.slice(0, colon) !== credentialId) continue
      return key.slice(colon + 1)
    }
    const colon = key.indexOf(':')
    if (colon < 0) continue
    return key.slice(colon + 1)
  }
  return null
}

export function resolveQuotaRuleModelIdentity(
  rule: QuotaRule,
  ctx?: QuotaRuleLabelContext
): QuotaRuleModelIdentity {
  const rawModelName = rule.key.model_name?.trim() ?? ''
  if (!rawModelName) {
    return { invokeName: null, upstreamName: null }
  }

  if (rule.key.layer === 'platform') {
    return {
      invokeName: rawModelName,
      upstreamName: findUpstreamNameForInvokeAlias(rawModelName, rule.key.credential_id, ctx),
    }
  }

  if (rule.key.layer === 'upstream') {
    const credentialId = rule.key.credential_id
    const invokeName = resolveInvokeNameForCredentialRealModel(
      credentialId,
      rawModelName,
      ctx?.modelRefByCredentialRealModel
    )
    return { invokeName, upstreamName: rawModelName }
  }

  return { invokeName: rawModelName, upstreamName: null }
}

export function formatQuotaRuleInvokeNameLabel(
  rule: QuotaRule,
  ctx?: QuotaRuleLabelContext
): string {
  if (!rule.key.model_name) return '（全模型）'
  if (rule.key.layer === 'platform') {
    return rule.key.model_name.trim()
  }
  const identity = resolveQuotaRuleModelIdentity(rule, ctx)
  if (identity.invokeName) return identity.invokeName
  if (ctx?.quotaModelLookupLoading) return '加载中…'
  // 上游 model_name 存 real_model；目录未命中时回退展示上游 id 短名
  const upstream = rule.key.model_name.trim()
  if (upstream) {
    const short = upstream.includes('/') ? upstream.split('/', 2)[1] : upstream
    return short ? `（未注册）${short}` : '（未注册调用名）'
  }
  return '（未注册调用名）'
}

export function formatQuotaRuleUpstreamNameLabel(
  rule: QuotaRule,
  ctx?: QuotaRuleLabelContext
): string {
  if (!rule.key.model_name) return '—'
  const identity = resolveQuotaRuleModelIdentity(rule, ctx)
  return identity.upstreamName ?? '—'
}

/** 配额中心「来源」列：优先 key.quota_label，下游回退 plan_label。 */
export function resolveQuotaRuleSourceLabel(rule: QuotaRule): string {
  const quotaLabel = rule.key.quota_label?.trim()
  if (quotaLabel) return quotaLabel
  const planLabel = quotaRuleLegacyPlanLabel(rule)
  if (planLabel) return planLabel
  return '自定义'
}

/**
 * 配额中心「模型」列：platform 用别名；upstream 用目录解析的 Gateway 别名，
 * 解析不到则回退上游 endpoint（`real_model`）。来源列见 resolveQuotaRuleSourceLabel。
 */
export function resolveQuotaRuleModelLabel(rule: QuotaRule, ctx?: QuotaRuleLabelContext): string {
  if (!rule.key.model_name) return '（全模型）'
  if (rule.key.layer === 'upstream') {
    const identity = resolveQuotaRuleModelIdentity(rule, ctx)
    return identity.invokeName ?? identity.upstreamName ?? rule.key.model_name
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

export function quotaUsageHasMetrics(usage: QuotaRuleUsage): boolean {
  return (
    usage.current_usd !== null || usage.current_tokens !== null || usage.current_requests !== null
  )
}

function formatQuotaTimestamp(iso: string): string {
  return new Date(iso).toLocaleString()
}

export function quotaUsageHasPeriodWindow(usage: QuotaRuleUsage | null | undefined): boolean {
  if (!usage) return false
  if (usage.reset_at ?? usage.budget_reset_at) return true
  return usage.window_start !== null
}

function formatRollingWindowLabel(windowSeconds: number): string {
  const hours = windowSeconds / 3600
  if (hours >= 1 && Number.isInteger(hours)) return `${String(hours)}h`
  return `${String(windowSeconds)}s`
}

/**
 * 是否为「真正的滚动窗口」（用量随时间连续滑动、无固定重置时刻）。
 *
 * 与后端 `is_sliding_rolling_window` 口径一致：仅 `window_seconds > 0` 且策略为 `rolling`
 * 才成立；`window_seconds <= 0` 的累计（总额）即便策略名是 `rolling` 也按固定累计处理
 * （可手工校正 / 清零）。展示判断、内联编辑器禁用等滚动特判统一以此为单一真源。
 */
export function isSlidingRollingWindow(rule: QuotaRule): boolean {
  return (
    rule.key.reset_strategy === 'rolling' &&
    rule.key.window_seconds !== null &&
    rule.key.window_seconds > 0
  )
}

/** 当前配额窗口起止（或累计/下次重置说明）。 */
export function formatQuotaRulePeriodWindow(rule: QuotaRule): string | null {
  const usage = rule.usage
  if (!usage) return null
  if (rule.key.period === 'total') {
    return '累计额度（不自动重置）'
  }
  // 滚动窗口随时间连续滑动、无固定重置时刻，不能渲染成「本周期 X—Y / 下次重置」。
  if (isSlidingRollingWindow(rule) && rule.key.window_seconds !== null) {
    return `滚动窗口 · 近 ${formatRollingWindowLabel(rule.key.window_seconds)}（随时间滚动，无固定重置）`
  }
  const start = usage.window_start
  const end = usage.reset_at ?? usage.budget_reset_at
  if (start && end) {
    return `本周期 ${formatQuotaTimestamp(start)} — ${formatQuotaTimestamp(end)}`
  }
  if (end) {
    return `下次重置 ${formatQuotaTimestamp(end)}`
  }
  if (start) {
    return `周期自 ${formatQuotaTimestamp(start)}`
  }
  return null
}

/** 起止时间（按行/规则维度）展示；两侧皆空返回 null（= 始终有效）。 */
export function formatQuotaRuleValidityRange(rule: QuotaRule): string | null {
  const from = rule.valid_from
  const until = rule.valid_until
  if (!from && !until) return null
  if (from && until) {
    return `${formatQuotaTimestamp(from)} — ${formatQuotaTimestamp(until)}`
  }
  if (from) return `${formatQuotaTimestamp(from)} 起`
  return until ? `至 ${formatQuotaTimestamp(until)}` : null
}

export function formatQuotaRuleResetAt(rule: QuotaRule): string | null {
  const at = rule.usage?.reset_at ?? rule.usage?.budget_reset_at
  if (!at) return null
  return formatQuotaTimestamp(at)
}

export function computeQuotaRuleUsageRatio(rule: QuotaRule): {
  ratio: number
  barColor: string
} {
  const usage = rule.usage
  const limitUsd = rule.limits.limit_usd
  const limitTok = rule.limits.limit_tokens
  const limitReq = rule.limits.limit_requests
  if (
    !usage ||
    !quotaUsageHasMetrics(usage) ||
    (limitUsd === null && limitTok === null && limitReq === null)
  ) {
    return { ratio: 0, barColor: 'bg-muted' }
  }
  const usdRatio =
    limitUsd !== null && limitUsd > 0 && usage.current_usd !== null
      ? parseQuotaNumeric(usage.current_usd) / parseQuotaNumeric(limitUsd)
      : 0
  const tokRatio =
    limitTok !== null && limitTok > 0 && usage.current_tokens !== null
      ? parseQuotaNumeric(usage.current_tokens) / parseQuotaNumeric(limitTok)
      : 0
  const reqRatio =
    limitReq !== null && limitReq > 0 && usage.current_requests !== null
      ? parseQuotaNumeric(usage.current_requests) / parseQuotaNumeric(limitReq)
      : 0
  const ratio = Math.max(usdRatio, tokRatio, reqRatio)
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
