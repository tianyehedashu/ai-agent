/** 与 backend GATEWAY_MODEL_TEST_SUPPORTED_CAPABILITIES 一致 */
import { GATEWAY_MODEL_TEST_SUPPORTED_CAPABILITIES } from '@/api/gateway'

/**
 * 网关页面通用 Scope Tab：与后端 `Team.kind` 字面量对齐。
 *
 * - `personal`：个人团队（每用户一个，单成员）
 * - `shared`：共享团队（多人协作）
 *
 * 与 `BudgetScope.team`、`CredentialScope.team`（写入归属层级）正交，
 * URL 字面量虽不同（`shared` vs `team`），语义相互独立。
 */
export type GatewayScopeTab = 'personal' | 'shared'

/** @deprecated 使用 `GatewayScopeTab`；保留单版本兼容旧 import。 */
export type ModelScopeTab = GatewayScopeTab

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

export type GatewayCapability = (typeof CAPABILITIES)[number]

/** 团队模型 capability 字段的中文展示（API 仍用英文枚举值） */
export const CAPABILITY_LABELS: Record<GatewayCapability, string> = {
  chat: '聊天 / 文本生成',
  embedding: '向量 Embedding',
  image: '图片理解',
  video_generation: '视频生成',
  moderation: '内容审核',
  audio_transcription: '语音转文字',
  audio_speech: '文字转语音',
  rerank: '重排序',
}

export function capabilityLabel(capability: string): string {
  if (capability in CAPABILITY_LABELS) {
    return CAPABILITY_LABELS[capability as GatewayCapability]
  }
  return capability
}

export const MODEL_TYPE_LABELS: Record<string, string> = {
  text: '文本',
  image: '视觉',
  image_gen: '生图',
  video: '视频',
}

export const TESTABLE_CAPABILITIES: ReadonlySet<string> = new Set(
  GATEWAY_MODEL_TEST_SUPPORTED_CAPABILITIES
)

/**
 * 批量「测试全部」产品范围（前端并发编排，无后端 batch API）：
 * - 团队：`GET /gateway/models` 注册行（需 Gateway 写权限）
 * - 个人：`GET /gateway/my-models` BYOK 行（登录用户本人）
 * - 不含：`GET /models/available` 系统目录（无注册行 id，探活策略未定义）
 */
export const BATCH_TEST_CONCURRENCY = 3

/** 与 backend domains.gateway.domain.types.RoutingStrategy 对齐 */
export const ROUTING_STRATEGIES = [
  'simple-shuffle',
  'least-busy',
  'usage-based-routing-v2',
  'latency-based-routing',
  'cost-based-routing',
] as const

export type RoutingStrategy = (typeof ROUTING_STRATEGIES)[number]

/** 路由策略中文展示（API 仍用英文枚举值） */
export const ROUTING_STRATEGY_LABELS: Record<RoutingStrategy, string> = {
  'simple-shuffle': '简单随机',
  'least-busy': '最少繁忙',
  'usage-based-routing-v2': '按用量路由',
  'latency-based-routing': '按延迟路由',
  'cost-based-routing': '按成本路由',
}

/** 历史路由数据可能仍存旧枚举值，仅用于展示 */
const ROUTING_STRATEGY_LEGACY_LABELS: Record<string, string> = {
  'usage-based-routing': '按用量路由',
}

export function routingStrategyLabel(strategy: string): string {
  if (strategy in ROUTING_STRATEGY_LABELS) {
    return ROUTING_STRATEGY_LABELS[strategy as RoutingStrategy]
  }
  return ROUTING_STRATEGY_LEGACY_LABELS[strategy] ?? strategy
}

export type HealthFilter = 'all' | 'success' | 'failed' | 'unknown'

export const USAGE_PERIOD_DAYS = [1, 7, 30] as const
export type UsagePeriodDays = (typeof USAGE_PERIOD_DAYS)[number]

export function parseScopeTab(raw: string | null): GatewayScopeTab {
  if (raw === 'personal') return 'personal'
  if (raw === 'shared') return 'shared'
  if (raw === 'team') return 'shared'
  return 'shared'
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
