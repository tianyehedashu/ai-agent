/**
 * Playground 按试调模式过滤模型列表（与 GatewayModel.capability / selector_capabilities 对齐）
 */

import type { ModelTestStatus } from '@/types/user-model'

export type PlaygroundMode = 'chat' | 'vision' | 'image_gen' | 'video_gen'

export interface ModelCandidate {
  name: string
  scope: 'team' | 'personal'
  status: ModelTestStatus
  capability: string
  selector_capabilities?: Record<string, unknown>
  model_types?: string[]
}

export const PLAYGROUND_MODE_LABELS: Record<PlaygroundMode, string> = {
  chat: '对话',
  vision: '视觉理解',
  image_gen: '图片生成',
  video_gen: '视频生成',
}

function flag(cap: Record<string, unknown> | undefined, key: string): boolean {
  return cap?.[key] === true
}

export function modelSupportsVision(m: ModelCandidate): boolean {
  if (flag(m.selector_capabilities, 'supports_vision')) return true
  return m.capability === 'chat' && (m.model_types?.includes('image') ?? false)
}

export function modelSupportsImageGen(m: ModelCandidate): boolean {
  if (m.capability === 'image') return true
  if (flag(m.selector_capabilities, 'supports_image_gen')) return true
  return m.model_types?.includes('image_gen') ?? false
}

export function modelSupportsVideoGen(m: ModelCandidate): boolean {
  if (m.capability === 'video_generation') return true
  if (flag(m.selector_capabilities, 'supports_video_gen')) return true
  return m.model_types?.includes('video') ?? false
}

export function filterModelsByMode(
  models: ModelCandidate[],
  mode: PlaygroundMode
): ModelCandidate[] {
  switch (mode) {
    case 'chat':
      return models.filter((m) => m.capability === 'chat')
    case 'vision':
      return models.filter(modelSupportsVision)
    case 'image_gen':
      return models.filter(modelSupportsImageGen)
    case 'video_gen':
      return models.filter(modelSupportsVideoGen)
    default: {
      const _exhaustive: never = mode
      return _exhaustive
    }
  }
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
}

export function buildModelCandidateIndex(
  candidateModels: readonly ModelCandidate[]
): Map<string, ModelCandidate> {
  return new Map(candidateModels.map((m) => [m.name, m]))
}

export function filterPlaygroundRouteCandidates(
  routes:
    | readonly { enabled: boolean; primary_models: string[]; virtual_model: string }[]
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
      if (!credentialId) return true
      return r.primary_models.length > 0 && r.primary_models.every((name) => modelNames.has(name))
    })
    .filter((r) => routeSupportsMode(r.primary_models, playgroundMode, modelsByName))
    .map((r) => ({ name: r.virtual_model, primaryModels: r.primary_models }))
    .sort((a, b) => a.name.localeCompare(b.name))
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
