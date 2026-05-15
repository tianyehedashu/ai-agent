import type { GatewayModel, GatewayModelPreset, GatewayRoute } from '@/api/gateway'
import type { ModelTestStatus } from '@/types/user-model'
import { MODEL_PROVIDERS } from '@/types/user-model'

import type { HealthFilter } from './constants'

export function channelLabel(id: string): string {
  return MODEL_PROVIDERS.find((p) => p.id === id)?.name ?? id
}

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

export function parseModelList(value: string): string[] {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter((item) => item.length > 0)
}

export function buildPresetTags(preset: GatewayModelPreset): Record<string, unknown> {
  return {
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
}

export function healthKey(status: ModelTestStatus): 'success' | 'failed' | 'unknown' {
  if (status === 'success') return 'success'
  if (status === 'failed') return 'failed'
  return 'unknown'
}

export function matchesHealthFilter(model: GatewayModel, filter: HealthFilter): boolean {
  if (filter === 'all') return true
  return healthKey(model.last_test_status) === filter
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
  return `${label} · ${String(requests)} 次 · ${String(tokens)} tok · $${coalesceNumber(costUsd).toFixed(4)}`
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

export function summarizeHealth(models: GatewayModel[]): {
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
