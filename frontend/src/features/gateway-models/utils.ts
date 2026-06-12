import { startTransition } from 'react'

import type {
  GatewayModel,
  GatewayModelPreset,
  GatewayModelRegistryScope,
  GatewayModelTestResult,
} from '@/api/gateway/models'
import type { GatewayRoute } from '@/api/gateway/routes'
import { invalidateGatewayRouteCaches } from '@/features/gateway-models/routes/query-keys'
import { formatMoney } from '@/lib/money'
import type { ModelTestStatus } from '@/types/user-model'
import { MODEL_PROVIDERS } from '@/types/user-model'

import {
  BATCH_TEST_CONCURRENCY,
  TESTABLE_CAPABILITIES,
  VIDEO_BATCH_TEST_CONCURRENCY,
  type HealthFilter,
} from './constants'
import { gatewayModelsByCredentialInvalidatePrefix } from './query-keys'

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
  credentialFilter = '',
  page = 1,
  pageSize = 20,
  search = '',
  healthFilter: HealthFilter = 'all',
  abilityFilter = ''
): readonly [
  'gateway',
  'models',
  string,
  GatewayModelRegistryScope,
  string,
  string,
  number,
  number,
  string,
  HealthFilter,
  string,
] {
  return [
    'gateway',
    'models',
    teamId,
    registryScope,
    providerFilter,
    credentialFilter,
    page,
    pageSize,
    search,
    healthFilter,
    abilityFilter,
  ]
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

/** 与后端不可用判定对齐：disabled / failed / entitlement 耗尽或过期 */
export function isModelUnavailable(model: ModelWithConnectivityStatus): boolean {
  const active = model.enabled ?? model.is_active ?? true
  if (!active) return true
  if (model.last_test_status === 'failed') return true
  const entitlement = model.entitlement_status
  return entitlement === 'exhausted' || entitlement === 'expired'
}

export function connectivitySummaryFromApi(
  summary:
    | {
        total: number
        available: number
        unavailable: number
        success: number
        failed: number
        unknown: number
      }
    | undefined,
  models: readonly ModelWithConnectivityStatus[]
): ReturnType<typeof summarizeHealth> {
  if (summary) {
    return {
      total: summary.total,
      success: summary.success,
      failed: summary.failed,
      unknown: summary.unknown,
    }
  }
  return summarizeHealth(models)
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

export function filterUntestedConnectivityModels<T extends ModelWithConnectivityStatus>(
  items: readonly T[]
): T[] {
  return filterTestableConnectivityModels(
    items.filter((m) => healthKey(m.last_test_status) === 'unknown')
  )
}

export function batchConnectivityIncludesVideoGeneration(
  items: readonly ModelWithConnectivityStatus[]
): boolean {
  return filterTestableConnectivityModels(items).some((m) => m.capability === 'video_generation')
}

function isConnectivityTestFailure(result: unknown): boolean {
  if (result === null || typeof result !== 'object' || !('success' in result)) {
    return false
  }
  return (result as { success?: boolean }).success === false
}

function isGatewayModelTestResult(result: unknown): result is GatewayModelTestResult {
  return (
    result !== null &&
    typeof result === 'object' &&
    'success' in result &&
    'status' in result &&
    'tested_at' in result
  )
}

/** 批量探活完成后写入列表 cache 的连通性字段 */
export interface ModelConnectivityPatchFields {
  last_test_status: ModelTestStatus
  last_tested_at: string | null
  last_test_reason: string | null
}

/** POST /models/{id}/test 响应 → 列表行 last_test_* 字段 */
export function connectivityFieldsFromTestResult(
  result: GatewayModelTestResult
): ModelConnectivityPatchFields {
  const last_test_status: ModelTestStatus =
    result.status === 'success' || result.status === 'failed'
      ? result.status
      : result.success
        ? 'success'
        : 'failed'
  return {
    last_test_status,
    last_tested_at: result.tested_at,
    last_test_reason: result.reason ?? null,
  }
}

function isModelListConnectivityCache(data: unknown): data is Array<{ id: string }> {
  return (
    Array.isArray(data) &&
    data.every(
      (item) =>
        item !== null && typeof item === 'object' && 'id' in item && 'last_test_status' in item
    )
  )
}

function isPaginatedModelListConnectivityCache(
  data: unknown
): data is { items: Array<{ id: string }> } {
  return (
    data !== null &&
    typeof data === 'object' &&
    'items' in data &&
    Array.isArray((data as { items: unknown }).items) &&
    (data as { items: unknown[] }).items.every(
      (item) =>
        item !== null && typeof item === 'object' && 'id' in item && 'last_test_status' in item
    )
  )
}

function patchModelListConnectivity<T extends { id: string }>(
  models: readonly T[],
  modelId: string,
  fields: ModelConnectivityPatchFields
): T[] {
  return models.map((m) => (m.id === modelId ? { ...m, ...fields } : m))
}

export type ModelListCacheScope = 'team' | 'personal'

/** 批量探活逐条完成后局部更新 React Query 中的模型列表 cache */
export function patchModelConnectivityInCache(
  queryClient: QueryClient,
  modelId: string,
  fields: ModelConnectivityPatchFields,
  scope: ModelListCacheScope
): void {
  const queryKey =
    scope === 'team' ? (['gateway', 'models'] as const) : (['gateway', 'my-models'] as const)
  startTransition(() => {
    queryClient.setQueriesData({ queryKey }, (old) => {
      if (isModelListConnectivityCache(old)) {
        return patchModelListConnectivity(old, modelId, fields)
      }
      if (isPaginatedModelListConnectivityCache(old)) {
        return {
          ...old,
          items: patchModelListConnectivity(old.items, modelId, fields),
        }
      }
      return old
    })
  })
}

/** 批量探活 `onItemComplete`：将 test 响应 patch 到 team / personal 列表 cache */
export function createBatchConnectivityCachePatcher(
  queryClient: QueryClient,
  scope: ModelListCacheScope
): (modelId: string, result: GatewayModelTestResult) => void {
  return (modelId, result) => {
    patchModelConnectivityInCache(
      queryClient,
      modelId,
      connectivityFieldsFromTestResult(result),
      scope
    )
  }
}

/** 对可探活注册行并发调用单条 test API（团队 / 个人管理面共用） */
export async function runBatchConnectivityTests(
  items: readonly ModelWithConnectivityStatus[],
  testById: (id: string) => Promise<unknown>,
  options?: {
    signal?: AbortSignal
    onProgress?: (done: number, total: number, failedIds: readonly string[]) => void
    onItemComplete?: (modelId: string, result: GatewayModelTestResult) => void
  }
): Promise<string[]> {
  const testable = filterTestableConnectivityModels(items)
  if (testable.length === 0) return []

  const videoItems = testable.filter((m) => m.capability === 'video_generation')
  const otherItems = testable.filter((m) => m.capability !== 'video_generation')
  const failed: string[] = []
  let done = 0
  const total = testable.length

  async function runOne(model: ModelWithConnectivityStatus): Promise<void> {
    if (options?.signal?.aborted) return
    try {
      const result = await testById(model.id)
      if (isGatewayModelTestResult(result)) {
        options?.onItemComplete?.(model.id, result)
      }
      if (isConnectivityTestFailure(result)) {
        failed.push(model.id)
      }
    } catch {
      failed.push(model.id)
    }
    done += 1
    options?.onProgress?.(done, total, failed)
  }

  await runWithConcurrency(otherItems, BATCH_TEST_CONCURRENCY, runOne, options?.signal)
  await runWithConcurrency(videoItems, VIDEO_BATCH_TEST_CONCURRENCY, runOne, options?.signal)

  return failed
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
  if (r.includes('暂不支持')) return '不支持探活'
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
  fn: (item: T) => Promise<unknown>,
  signal?: AbortSignal
): Promise<void> {
  if (items.length === 0) return
  const limit = Math.max(1, Math.min(concurrency, items.length))
  let next = 0
  async function worker(): Promise<void> {
    for (;;) {
      if (signal?.aborted) return
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
  void queryClient.invalidateQueries({ queryKey: ['gateway', 'managed-team-models'] })
  void queryClient.invalidateQueries({ queryKey: ['gateway', 'unified-models'] })
  if (options?.credentialId) {
    void queryClient.invalidateQueries({
      queryKey: gatewayModelsByCredentialInvalidatePrefix(options.credentialId),
    })
  }
  if (options?.usageSummary) {
    void queryClient.invalidateQueries({ queryKey: ['gateway', 'models', 'usage-summary'] })
  }
}

/** 注册别名变更后，刷新虚拟路由与 vkey 白名单（后端会级联更新引用） */
export function invalidateGatewayModelAliasDependents(queryClient: QueryClient): void {
  invalidateGatewayRouteCaches(queryClient)
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

/** 删除全部探活失败模型的确认文案 */
export function formatDeleteFailedConfirmLabel(count: number, names: readonly string[]): string {
  if (count === 0) return ''
  const listed =
    names.length <= 10
      ? names.join('、')
      : `${names.slice(0, 8).join('、')} 以及 ${String(names.length - 8)} 个其他`
  return `确定删除 ${String(count)} 个探活失败的模型？\n${listed}\n\n将同步更新虚拟 Key / 路由中的模型白名单，并清理相关授权与预算行。此操作不可撤销。`
}

export const BATCH_DELETE_MAX = 200

/** 与后端 PersonalModelBatchImportRequest.items max_length 对齐 */
export const BATCH_IMPORT_MAX = 50

export interface PersonalModelBatchImportItem {
  upstream_model_id: string
  model_types: string[]
}

/** 将批量导入 items 按上限分块 */
export function chunkBatchImportItems(
  items: readonly PersonalModelBatchImportItem[],
  max = BATCH_IMPORT_MAX
): PersonalModelBatchImportItem[][] {
  if (items.length === 0) return []
  const chunks: PersonalModelBatchImportItem[][] = []
  for (let i = 0; i < items.length; i += max) {
    chunks.push(items.slice(i, i + max))
  }
  return chunks
}

/** 探活失败且允许删除的模型 */
export function filterDeletableFailedModels<T extends ModelWithConnectivityStatus>(
  models: readonly T[],
  canDelete: (model: T) => boolean
): T[] {
  return models.filter((m) => m.last_test_status === 'failed' && canDelete(m))
}

/** 将 ID 列表按单次 batch 操作上限分块 */
export function chunkIdsForBatchOperation(
  ids: readonly string[],
  max = BATCH_DELETE_MAX
): string[][] {
  if (ids.length === 0) return []
  const chunks: string[][] = []
  for (let i = 0; i < ids.length; i += max) {
    chunks.push(ids.slice(i, i + max))
  }
  return chunks
}

/** @deprecated 使用 chunkIdsForBatchOperation */
export function chunkIdsForBatchDelete(ids: readonly string[], max = BATCH_DELETE_MAX): string[][] {
  return chunkIdsForBatchOperation(ids, max)
}

/** 将勾选集限制在当前可见列表内（渲染期派生，避免 effect 同步） */
export function filterSelectedIdsInView(
  selectedIds: ReadonlySet<string>,
  visibleIds: ReadonlySet<string>
): Set<string> {
  const next = new Set<string>()
  for (const id of selectedIds) {
    if (visibleIds.has(id)) next.add(id)
  }
  return next
}

export interface BatchDeleteChunkResult {
  succeeded: string[]
  failed: Array<{ id: string; code: string; message: string }>
  grants_removed: number
  budgets_removed: number
}

/** 顺序执行多批 batch-delete 并合并结果 */
export async function runChunkedBatchDelete(
  ids: readonly string[],
  mutateFn: (chunk: string[]) => Promise<BatchDeleteChunkResult>,
  chunkSize = BATCH_DELETE_MAX
): Promise<BatchDeleteChunkResult> {
  const chunks = chunkIdsForBatchOperation(ids, chunkSize)
  const merged: BatchDeleteChunkResult = {
    succeeded: [],
    failed: [],
    grants_removed: 0,
    budgets_removed: 0,
  }
  for (const chunk of chunks) {
    const result = await mutateFn(chunk)
    merged.succeeded.push(...result.succeeded)
    merged.failed.push(...result.failed)
    merged.grants_removed += result.grants_removed
    merged.budgets_removed += result.budgets_removed
  }
  return merged
}

export interface BatchResyncChunkResult {
  succeeded: string[]
  failed: Array<{ id: string; code: string; message: string }>
}

/** 顺序执行多批 batch-resync-capabilities 并合并结果 */
export async function runChunkedBatchResync(
  ids: readonly string[],
  mutateFn: (chunk: string[]) => Promise<BatchResyncChunkResult>,
  chunkSize = BATCH_DELETE_MAX
): Promise<BatchResyncChunkResult> {
  const chunks = chunkIdsForBatchOperation(ids, chunkSize)
  const merged: BatchResyncChunkResult = {
    succeeded: [],
    failed: [],
  }
  for (const chunk of chunks) {
    const result = await mutateFn(chunk)
    merged.succeeded.push(...result.succeeded)
    merged.failed.push(...result.failed)
  }
  return merged
}

/** 可执行 LiteLLM 能力 resync 的模型（与批量删除权限一致） */
export function filterResyncableCapabilityModels<T extends GatewayModel>(
  models: readonly T[],
  canResync: (model: T) => boolean
): T[] {
  return models.filter(canResync)
}

/** 解析团队模型归属 tenant（跨团队 batch 路由用） */
export function resolveGatewayModelTeamId(
  model: Pick<GatewayModel, 'tenant_id' | 'team_id'>
): string | null {
  const tenantId = model.tenant_id ?? model.team_id
  if (typeof tenantId === 'string' && tenantId !== '') return tenantId
  return null
}

/** 按 tenant 分组模型（跨团队 batch delete/resync 编排） */
export function groupModelsByTeamId(models: readonly GatewayModel[]): Map<string, GatewayModel[]> {
  const map = new Map<string, GatewayModel[]>()
  for (const model of models) {
    const teamId = resolveGatewayModelTeamId(model)
    if (!teamId) continue
    const existing = map.get(teamId)
    if (existing) {
      existing.push(model)
    } else {
      map.set(teamId, [model])
    }
  }
  return map
}

/** 按 tenant 分组模型 id（跨团队 batch 已缓存 team 归属时使用） */
export function groupModelIdsByTeamId(
  ids: readonly string[],
  resolveTeamId: (id: string) => string | null
): Map<string, string[]> {
  const map = new Map<string, string[]>()
  for (const id of ids) {
    const teamId = resolveTeamId(id)
    if (!teamId) continue
    const existing = map.get(teamId)
    if (existing) {
      existing.push(id)
    } else {
      map.set(teamId, [id])
    }
  }
  return map
}

/** 跨 tenant 顺序 batch-delete：先按 team 分组再 chunk */
export async function runChunkedBatchDeleteByTeam(
  models: readonly GatewayModel[],
  deleteChunkForTeam: (teamId: string, chunk: string[]) => Promise<BatchDeleteChunkResult>,
  chunkSize = BATCH_DELETE_MAX
): Promise<BatchDeleteChunkResult> {
  const idsByTeam = new Map<string, string[]>()
  for (const [teamId, teamModels] of groupModelsByTeamId(models)) {
    idsByTeam.set(
      teamId,
      teamModels.map((m) => m.id)
    )
  }
  return runChunkedBatchDeleteByTeamIds(idsByTeam, deleteChunkForTeam, chunkSize)
}

/** 跨 tenant 顺序 batch-delete（已知 team 归属的 id 分组） */
export async function runChunkedBatchDeleteByTeamIds(
  idsByTeam: ReadonlyMap<string, readonly string[]>,
  deleteChunkForTeam: (teamId: string, chunk: string[]) => Promise<BatchDeleteChunkResult>,
  chunkSize = BATCH_DELETE_MAX
): Promise<BatchDeleteChunkResult> {
  const merged: BatchDeleteChunkResult = {
    succeeded: [],
    failed: [],
    grants_removed: 0,
    budgets_removed: 0,
  }
  for (const [teamId, ids] of idsByTeam) {
    const result = await runChunkedBatchDelete(
      ids,
      (chunk) => deleteChunkForTeam(teamId, chunk),
      chunkSize
    )
    merged.succeeded.push(...result.succeeded)
    merged.failed.push(...result.failed)
    merged.grants_removed += result.grants_removed
    merged.budgets_removed += result.budgets_removed
  }
  return merged
}

/** 跨 tenant 顺序 batch-resync：先按 team 分组再 chunk */
export async function runChunkedBatchResyncByTeam(
  models: readonly GatewayModel[],
  resyncChunkForTeam: (teamId: string, chunk: string[]) => Promise<BatchResyncChunkResult>,
  chunkSize = BATCH_DELETE_MAX
): Promise<BatchResyncChunkResult> {
  const idsByTeam = new Map<string, string[]>()
  for (const [teamId, teamModels] of groupModelsByTeamId(models)) {
    idsByTeam.set(
      teamId,
      teamModels.map((m) => m.id)
    )
  }
  return runChunkedBatchResyncByTeamIds(idsByTeam, resyncChunkForTeam, chunkSize)
}

/** 跨 tenant 顺序 batch-resync（已知 team 归属的 id 分组） */
export async function runChunkedBatchResyncByTeamIds(
  idsByTeam: ReadonlyMap<string, readonly string[]>,
  resyncChunkForTeam: (teamId: string, chunk: string[]) => Promise<BatchResyncChunkResult>,
  chunkSize = BATCH_DELETE_MAX
): Promise<BatchResyncChunkResult> {
  const merged: BatchResyncChunkResult = {
    succeeded: [],
    failed: [],
  }
  for (const [teamId, ids] of idsByTeam) {
    const result = await runChunkedBatchResync(
      ids,
      (chunk) => resyncChunkForTeam(teamId, chunk),
      chunkSize
    )
    merged.succeeded.push(...result.succeeded)
    merged.failed.push(...result.failed)
  }
  return merged
}

/** 跨团队批量探活：按 model id 解析 tenant 后路由 test API */
export function createManagedTeamsTestById(
  models: readonly GatewayModel[],
  testModel: (teamId: string, id: string) => Promise<GatewayModelTestResult>
): (id: string) => Promise<GatewayModelTestResult> {
  const teamByModelId = new Map<string, string>()
  for (const model of models) {
    const teamId = resolveGatewayModelTeamId(model)
    if (teamId) teamByModelId.set(model.id, teamId)
  }
  return (id: string) => {
    const teamId = teamByModelId.get(id)
    if (!teamId) {
      return Promise.reject(new Error(`无法解析模型 ${id} 的团队归属`))
    }
    return testModel(teamId, id)
  }
}

/** 可探活且当前用户可 update 的模型（跨团队 batch test 前置过滤） */
export function filterManageableTestableModels<T extends GatewayModel>(
  models: readonly T[],
  canManage: (model: T) => boolean
): T[] {
  return filterTestableConnectivityModels(models).filter(canManage)
}
