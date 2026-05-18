/** 与 backend GATEWAY_MODEL_TEST_SUPPORTED_CAPABILITIES 一致 */
import { GATEWAY_MODEL_TEST_SUPPORTED_CAPABILITIES } from '@/api/gateway'

export type ModelScopeTab = 'personal' | 'team'

export const MANUAL_PRESET = '__manual__'
export const NO_CREDENTIAL = '__none__'
export const FILTER_ALL = '__all__'
export const FILTER_ALL_STATUS = '__all_status__'

export const CAPABILITIES = [
  'chat',
  'embedding',
  'image',
  'video_generation',
  'moderation',
  'audio_transcription',
  'audio_speech',
  'rerank',
] as const

export const MODEL_TYPE_LABELS: Record<string, string> = {
  text: '文本',
  image: '视觉',
  image_gen: '生图',
  video: '视频',
}

export const TESTABLE_CAPABILITIES: ReadonlySet<string> = new Set(
  GATEWAY_MODEL_TEST_SUPPORTED_CAPABILITIES
)

export const ROUTING_STRATEGIES = [
  'simple-shuffle',
  'least-busy',
  'usage-based-routing',
  'latency-based-routing',
  'cost-based-routing',
] as const

export type HealthFilter = 'all' | 'success' | 'failed' | 'unknown'

export const USAGE_PERIOD_DAYS = [1, 7, 30] as const
export type UsagePeriodDays = (typeof USAGE_PERIOD_DAYS)[number]

export function parseScopeTab(raw: string | null): ModelScopeTab {
  return raw === 'personal' || raw === 'team' ? raw : 'team'
}

/** 模型页子视图：清单 / 注册 / 编辑（个人详情深链） */
export type ModelsPageView = 'list' | 'register' | 'edit'

export function parseModelsPageView(raw: string | null): ModelsPageView {
  if (raw === 'register') return 'register'
  if (raw === 'edit') return 'edit'
  return 'list'
}

/** @deprecated 使用 ModelsPageView */
export type TeamModelsView = 'list' | 'register'

/** @deprecated 使用 parseModelsPageView */
export function parseTeamModelsView(raw: string | null): 'list' | 'register' {
  const v = parseModelsPageView(raw)
  return v === 'edit' ? 'list' : v
}
