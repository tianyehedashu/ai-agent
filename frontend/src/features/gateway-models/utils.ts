import type {
  GatewayModel,
  GatewayModelPreset,
  GatewayModelRegistryScope,
} from '@/api/gateway/models'
import type { GatewayRoute } from '@/api/gateway/routes'
import { formatMoney } from '@/lib/money'
import type { ModelTestStatus } from '@/types/user-model'
import { MODEL_PROVIDERS } from '@/types/user-model'

import { BATCH_TEST_CONCURRENCY, TESTABLE_CAPABILITIES, type HealthFilter } from './constants'

import type { QueryClient } from '@tanstack/react-query'

/** 连通性健康统计 / 批量探活所需的最小字段 */
export interface ModelWithConnectivityStatus {
  id: string
  capability: string
  last_test_status: ModelTestStatus
  enabled?: boolean
  is_active?: boolean
  entitlement_status?: 'active' | 'exhausted' | 'resetting' | 'expired' | 'none'
}

/**
 * 管理面 ``registry_scope=requestable``：已启用且连通性探活未 failed。
 * 与后端 ``is_connectivity_requestable`` + ``only_enabled`` 对齐。
 */
export function isRegistryRequestableModel(model: ModelWithConnectivityStatus): boolean {
  const active = model.enabled ?? model.is_active ?? false
  if (!active) return false
  if (model.last_test_status === 'failed') return false
  return true
}

export function filterRegistryRequestableModels<T extends ModelWithConnectivityStatus>(
  items: readonly T[]
): T[] {
  return items.filter(isRegistryRequestableModel)
}

/**
 * 代理端 ``gateway.callable`` / ``compute_model_callable``：在 registry 可请求基础上，
 * 排除 entitlement 耗尽或过期（需条目带 ``entitlement_status``，如个人模型列表）。
 */
export function isProxyCallableModel(model: ModelWithConnectivityStatus): boolean {
  if (!isRegistryRequestableModel(model)) return false
  const entitlement = model.entitlement_status
  if (entitlement === 'exhausted' || entitlement === 'expired') return false
  return true
}

export function filterProxyCallableModels<T extends ModelWithConnectivityStatus>(
  items: readonly T[]
): T[] {
  return items.filter(isProxyCallableModel)
}

/** 接入通道 id → 展示名（模块级 Map，避免列表内反复线性查找） */
const MODEL_PROVIDER_NAME_BY_ID: ReadonlyMap<string, string> = new Map(
  MODEL_PROVIDERS.map((p) => [p.id, p.name])
)

/** 注册表查询范围（与后端 ``registry_scope`` 对齐） */
export type { GatewayModelRegistryScope } from '@/api/gateway/models'

/** 团队模型列表模式（与 ``TeamModelsWorkspace.listMode`` 对齐） */
export type TeamModelsListMode = 'team' | 'system'

/**
 * 团队模型列表 / 详情共用的 ``registry_scope`` 解析（与 ``TeamModelsWorkspace`` 一致）。
 *
 * - 凭据筛选：callable（合并列表）
 * - 系统 Tab：system
 * - 共享 Tab：team（租户注册表）
 */
export function resolveTeamModelsRegistryScope(
  listMode: TeamModelsListMode | undefined,
  credentialFilter: string
): GatewayModelRegistryScope {
  if (credentialFilter !== '') return 'callable'
  if (listMode === 'system') return 'system'
  return 'team'
}

/** 无 channel 筛选的个人模型列表 */
export const GATEWAY_MY_MODELS_ALL_QUERY_KEY = ['gateway', 'my-models'] as const

/** 无凭据筛选时的 requestable 列表 query key（TeamModelsWorkspace 等） */
export function gatewayModelsRequestableQueryKey(
  teamId: string,
  credentialFilter = ''
): ReturnType<typeof gatewayModelsListQueryKey> {
  return gatewayModelsListQueryKey(teamId, 'requestable', '', credentialFilter)
}

/**
 * Playground / Guide 团队模型列表 scope：无凭据用 requestable，有凭据用 callable（与 TeamModelsWorkspace 一致）。
 */
export function resolvePlaygroundTeamRegistryScope(
  credentialFilter: string
): GatewayModelRegistryScope {
  return credentialFilter !== ''
    ? resolveTeamModelsRegistryScope(undefined, credentialFilter)
    : 'requestable'
}

/** Playground / Guide 团队模型 query key（scope 随凭据筛选自动切换） */
export function playgroundTeamModelsQueryKey(
  teamId: string,
  credentialFilter = ''
): ReturnType<typeof gatewayModelsListQueryKey> {
  return gatewayModelsListQueryKey(
    teamId,
    resolvePlaygroundTeamRegistryScope(credentialFilter),
    '',
    credentialFilter
  )
}

/** 与 TeamModelsWorkspace listModels 查询键一致 */
export function gatewayModelsListQueryKey(
  teamId: string,
  registryScope: GatewayModelRegistryScope = 'team',
  providerFilter = '',
  credentialFilter = ''
): readonly ['gateway', 'models', string, GatewayModelRegistryScope, string, string] {
  return ['gateway', 'models', teamId, registryScope, providerFilter, credentialFilter]
}

export function channelLabel(id: string): string {
  return MODEL_PROVIDER_NAME_BY_ID.get(id) ?? id
}

/** 已启用注册模型（虚拟路由模型池） */
export function enabledGatewayModels(models: readonly GatewayModel[]): GatewayModel[] {
  return models.filter((m) => m.enabled)
}

/** @deprecated 使用 enabledGatewayModels */
export function enabledGatewayModelNames(models: readonly GatewayModel[]): string[] {
  return enabledGatewayModels(models).map((m) => m.name)
}

/** React Query：与 ModelSelector 一致的模型列表缓存时间 */
export const GATEWAY_MODELS_STALE_MS = 30_000

/** 与概览页一致：对齐后端 Decimal / JSON 数字 */
export function coalesceNumber(value: unknown): number {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string' && value.trim() !== '') {
    const n = Number(value)
    if (Number.isFinite(n)) return n
  }
  return 0
}

export function parsePositiveInt(value: string): number | null {
  const trimmed = value.trim()
  if (!trimmed) return null
  const parsed = Number.parseInt(trimmed, 10)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null
}

/** 比较字符串数组（顺序敏感） */
export function stringArraysEqual(a: readonly string[], b: readonly string[]): boolean {
  if (a.length !== b.length) return false
  return a.every((item, i) => item === b[i])
}

/** 从列表中剔除与主模型池重叠的别名（提交 Fallback 前调用） */
export function excludeModelsFromList(
  list: readonly string[],
  exclude: readonly string[]
): string[] {
  if (exclude.length === 0) return [...list]
  const excludeSet = new Set(exclude)
  return list.filter((n) => !excludeSet.has(n))
}

/** 有序模型池：勾选加入末尾 */
export function toggleOrderedModelList(
  prev: readonly string[],
  name: string,
  checked: boolean
): string[] {
  if (checked) return prev.includes(name) ? [...prev] : [...prev, name]
  return prev.filter((n) => n !== name)
}

/** 有序模型池：上移 / 下移 */
export function moveOrderedModelList(
  prev: readonly string[],
  index: number,
  dir: -1 | 1
): string[] {
  const next = [...prev]
  const j = index + dir
  if (j < 0 || j >= next.length) return next
  const tmp = next[index]
  next[index] = next[j]
  next[j] = tmp
  return next
}

/** 无序模型池：勾选切换 */
export function toggleModelSet(prev: readonly string[], name: string, checked: boolean): string[] {
  if (checked) return prev.includes(name) ? [...prev] : [...prev, name]
  return prev.filter((n) => n !== name)
}

export function buildPresetTags(preset: GatewayModelPreset): Record<string, unknown> {
  const thinkingParam = preset.selector_capabilities?.thinking_param
  const tags: Record<string, unknown> = {
    display_name: preset.name,
    description: preset.description,
    context_window: preset.context_window,
    input_price: preset.input_price,
    output_price: preset.output_price,
    supports_vision: preset.supports_vision,
    supports_tools: preset.supports_tools,
    supports_reasoning: preset.supports_reasoning,
    recommended_for: preset.recommended_for,
  }
  if (typeof thinkingParam === 'string') {
    tags.thinking_param = thinkingParam
  }
  return tags
}

export function healthKey(status: ModelTestStatus): 'success' | 'failed' | 'unknown' {
  if (status === 'success') return 'success'
  if (status === 'failed') return 'failed'
  return 'unknown'
}

export function matchesHealthFilter(
  model: ModelWithConnectivityStatus,
  filter: HealthFilter
): boolean {
  if (filter === 'all') return true
  return healthKey(model.last_test_status) === filter
}

export function filterTestableConnectivityModels<T extends ModelWithConnectivityStatus>(
  items: readonly T[]
): T[] {
  return items.filter((m) => TESTABLE_CAPABILITIES.has(m.capability))
}

/** 对可探活注册行并发调用单条 test API（团队 / 个人管理面共用） */
export async function runBatchConnectivityTests(
  items: readonly ModelWithConnectivityStatus[],
  testById: (id: string) => Promise<unknown>
): Promise<void> {
  const testable = filterTestableConnectivityModels(items)
  if (testable.length === 0) return
  await runWithConcurrency(testable, BATCH_TEST_CONCURRENCY, (m) => testById(m.id))
}

/** 将长错误归类为清单行短标签 */
export function classifyFailureReason(reason: string | null | undefined): string {
  const r = reason?.trim().toLowerCase() ?? ''
  if (!r) return '连接失败'
  if (
    r.includes('quota') ||
    r.includes('额度') ||
    r.includes('exhausted') ||
    r.includes('free tier')
  ) {
    return '额度或配额'
  }
  if (
    r.includes('credential') ||
    r.includes('api key') ||
    r.includes('unauthorized') ||
    r.includes('401')
  ) {
    return '凭据无效'
  }
  if (r.includes('timeout') || r.includes('timed out')) return '超时'
  if (r.includes('rate limit') || r.includes('429')) return '限流'
  if (r.includes('not found') || r.includes('404')) return '模型不存在'
  return '连接失败'
}

export function formatUsageLine(
  days: number,
  requests: number,
  tokens: number,
  costUsd: unknown
): string {
  const label = days === 1 ? '24h' : `${String(days)}d`
  const costStr = formatMoney(coalesceNumber(costUsd), { currency: 'CNY', precision: 4 })
  return `${label} · ${String(requests)} 次 · ${String(tokens)} tok · ${costStr}`
}

/** 反查引用某注册别名的虚拟路由 */
export function routesReferencingModel(routes: GatewayRoute[], modelName: string): GatewayRoute[] {
  return routes.filter(
    (route) =>
      route.primary_models.includes(modelName) ||
      route.fallbacks_general.includes(modelName) ||
      route.fallbacks_content_policy.includes(modelName) ||
      route.fallbacks_context_window.includes(modelName)
  )
}

/** 以固定并发度执行异步任务（用于批量测试等） */
export async function runWithConcurrency<T>(
  items: readonly T[],
  concurrency: number,
  fn: (item: T) => Promise<unknown>
): Promise<void> {
  if (items.length === 0) return
  const limit = Math.max(1, Math.min(concurrency, items.length))
  let next = 0
  async function worker(): Promise<void> {
    for (;;) {
      const i = next++
      if (i >= items.length) return
      await fn(items[i])
    }
  }
  await Promise.all(Array.from({ length: limit }, () => worker()))
}

/** 详情面板默认选中：深链优先，保留当前选中，再优先已启用且连通正常的模型 */
export function pickInspectorModelId(
  candidates: readonly GatewayModel[],
  currentId: string | null,
  preferredId?: string | null
): string | null {
  if (candidates.length === 0) return null

  const contains = (id: string): boolean => candidates.some((m) => m.id === id)

  if (preferredId && contains(preferredId)) return preferredId
  if (currentId && contains(currentId)) return currentId

  const pool = candidates.filter((m) => m.enabled)
  const ordered = pool.length > 0 ? pool : [...candidates]

  const success = ordered.find((m) => m.last_test_status === 'success')
  if (success) return success.id

  const untested = ordered.find((m) => m.last_test_status === null)
  if (untested) return untested.id

  return ordered[0]?.id ?? null
}

export function summarizeHealth(models: readonly ModelWithConnectivityStatus[]): {
  total: number
  success: number
  failed: number
  unknown: number
} {
  let success = 0
  let failed = 0
  let unknown = 0
  for (const m of models) {
    const k = healthKey(m.last_test_status)
    if (k === 'success') success += 1
    else if (k === 'failed') failed += 1
    else unknown += 1
  }
  return { total: models.length, success, failed, unknown }
}

/** 刷新模型列表相关 React Query 缓存 */
export function invalidateGatewayModelCaches(
  queryClient: QueryClient,
  options?: { credentialId?: string; usageSummary?: boolean }
): void {
  void queryClient.invalidateQueries({ queryKey: ['gateway', 'models'] })
  if (options?.credentialId) {
    void queryClient.invalidateQueries({
      queryKey: ['gateway', 'models', 'by-credential', options.credentialId],
    })
  }
  if (options?.usageSummary) {
    void queryClient.invalidateQueries({ queryKey: ['gateway', 'models', 'usage-summary'] })
  }
}

/** 注册别名变更后，刷新虚拟路由与 vkey 白名单（后端会级联更新引用） */
export function invalidateGatewayModelAliasDependents(queryClient: QueryClient): void {
  void queryClient.invalidateQueries({ queryKey: ['gateway', 'routes'] })
  void queryClient.invalidateQueries({ queryKey: ['gateway', 'keys'] })
}

/** 批量删除确认文案：列出模型名（>10 时折叠） */
export function formatBatchDeleteConfirmLabel(names: readonly string[]): string {
  if (names.length === 0) return ''
  const listed =
    names.length <= 10
      ? names.join('、')
      : `${names.slice(0, 8).join('、')} 以及 ${String(names.length - 8)} 个其他`
  return `确定删除以下 ${String(names.length)} 个模型？\n${listed}\n\n将同步更新虚拟 Key / 路由中的模型白名单，并清理相关授权与预算行。此操作不可撤销。`
}
