/**
 * Playground 按试调模式过滤模型列表（与 GatewayModel.model_types 对齐；API 已推导）
 */

import type { ModelTestStatus } from '@/types/user-model'

export type PlaygroundMode = 'chat' | 'vision' | 'image_gen' | 'video_gen'

export interface ModelCandidate {
  name: string
  scope: 'team' | 'personal'
  status: ModelTestStatus
  capability: string
  /** 注册行厂商（生图尺寸预设应与模型 provider 对齐，不能只看凭据筛选） */
  provider: string
  /** multi-grant vkey GET /v1/models：个人（主属 team）为 null，跨 team 为 slug */
  teamSlug?: string | null
  selector_capabilities?: Record<string, unknown>
  model_types?: string[]
}

export const PLAYGROUND_MODE_LABELS: Record<PlaygroundMode, string> = {
  chat: '对话',
  vision: '视觉理解',
  image_gen: '图片生成',
  video_gen: '视频生成',
}

/** Playground 模式 → 注册表列表 ``?type=``（与后端 policy 一致） */
export function playgroundModeToRegistryType(mode: PlaygroundMode): string {
  switch (mode) {
    case 'chat':
      return 'text'
    case 'vision':
      return 'image'
    case 'image_gen':
      return 'image_gen'
    case 'video_gen':
      return 'video'
    default: {
      const _exhaustive: never = mode
      return _exhaustive
    }
  }
}

function hasModelType(m: ModelCandidate, type: string): boolean {
  const types = m.model_types
  if (types && types.length > 0) {
    return types.includes(type)
  }
  return legacyModelSupportsType(m, type)
}

/** 无 model_types 时的兼容回退（旧数据或尚未 resync） */
function legacyModelSupportsType(m: ModelCandidate, type: string): boolean {
  const cap = m.selector_capabilities
  if (type === 'image') {
    return cap?.supports_vision === true || m.capability === 'chat'
  }
  if (type === 'image_gen') {
    return m.capability === 'image' || cap?.supports_image_gen === true
  }
  if (type === 'video') {
    return m.capability === 'video_generation' || cap?.supports_video_gen === true
  }
  if (type === 'text') {
    return m.capability === 'chat'
  }
  return false
}

export function modelSupportsVision(m: ModelCandidate): boolean {
  return hasModelType(m, 'image')
}

export function modelSupportsImageGen(m: ModelCandidate): boolean {
  return hasModelType(m, 'image_gen')
}

export function modelSupportsVideoGen(m: ModelCandidate): boolean {
  return hasModelType(m, 'video')
}

export function filterModelsByMode(
  models: ModelCandidate[],
  mode: PlaygroundMode
): ModelCandidate[] {
  const type = playgroundModeToRegistryType(mode)
  return models.filter((m) => hasModelType(m, type))
}

export function routeSupportsMode(
  primaryModels: string[],
  mode: PlaygroundMode,
  modelsByName: Map<string, ModelCandidate>
): boolean {
  if (mode === 'chat') return true
  for (const name of primaryModels) {
    const candidate = modelsByName.get(name)
    if (!candidate) continue
    if (mode === 'vision' && modelSupportsVision(candidate)) return true
    if (mode === 'image_gen' && modelSupportsImageGen(candidate)) return true
    if (mode === 'video_gen' && modelSupportsVideoGen(candidate)) return true
  }
  return false
}

export interface PlaygroundRouteCandidate {
  name: string
  primaryModels: string[]
  kind?: 'owned' | 'shared'
  ownerDisplay?: string | null
}

export function buildModelCandidateIndex(
  candidateModels: readonly ModelCandidate[]
): Map<string, ModelCandidate> {
  return new Map(candidateModels.map((m) => [m.name, m]))
}

export function filterPlaygroundRouteCandidates(
  routes:
    | readonly {
        enabled: boolean
        primary_models: string[]
        virtual_model: string
        isSharedRoute?: boolean
        ownerDisplay?: string | null
      }[]
    | undefined,
  credentialId: string,
  candidateModels: readonly ModelCandidate[],
  playgroundMode: PlaygroundMode,
  modelsByName: Map<string, ModelCandidate> = buildModelCandidateIndex(candidateModels)
): PlaygroundRouteCandidate[] {
  const modelNames = new Set(candidateModels.map((m) => m.name))
  return (routes ?? [])
    .filter((r) => r.enabled)
    .filter((r) => {
      if (r.primary_models.length === 0) return false
      // 未选凭据：直接展示已配置主模型的路由，不等待模型分页加载
      if (!credentialId) return true
      // 共享路由主模型可能在 owner 个人池，消费团队模型列表未必包含
      if (r.isSharedRoute) return true
      return r.primary_models.every((name) => modelNames.has(name))
    })
    .filter((r) => routeSupportsMode(r.primary_models, playgroundMode, modelsByName))
    .map((r) => ({
      name: r.virtual_model,
      primaryModels: r.primary_models,
      kind: r.isSharedRoute ? ('shared' as const) : ('owned' as const),
      ownerDisplay: r.ownerDisplay ?? null,
    }))
    .sort((a, b) => a.name.localeCompare(b.name))
}

/** 选中虚拟路由时预加载其主模型；否则按模型名翻页 */
export function ensurePlaygroundSelectionModelLoaded(
  selectedName: string,
  routeCandidates: readonly PlaygroundRouteCandidate[],
  ensureModelNameLoaded: (modelName: string) => void,
  rawRoutes?: readonly { virtual_model: string; primary_models: readonly string[] }[]
): void {
  const trimmed = selectedName.trim()
  if (!trimmed) return
  const route = routeCandidates.find((r) => r.name === trimmed)
  if (route) {
    for (const primary of route.primaryModels) {
      ensureModelNameLoaded(primary)
    }
    return
  }
  const rawRoute = rawRoutes?.find((r) => r.virtual_model === trimmed)
  if (rawRoute) {
    for (const primary of rawRoute.primary_models) {
      ensureModelNameLoaded(primary)
    }
    return
  }
  ensureModelNameLoaded(trimmed)
}

export function endpointPathForMode(
  mode: PlaygroundMode,
  apiFlavor: 'openai' | 'anthropic'
): string {
  if (mode === 'chat' && apiFlavor === 'anthropic') return '/messages'
  if (mode === 'chat' || mode === 'vision') return '/chat/completions'
  if (mode === 'image_gen') return '/images/generations'
  return '/videos'
}
