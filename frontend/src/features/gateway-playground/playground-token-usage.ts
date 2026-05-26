/**
 * Playground 试调结果 Token 用量解析（展示层纯函数）
 */

import type { PlaygroundMetadata } from './types'

export interface PlaygroundTokenUsage {
  total: number
  prompt?: number
  completion?: number
}

export function resolvePlaygroundTokenUsage(
  metadata: Pick<PlaygroundMetadata, 'totalTokens' | 'promptTokens' | 'completionTokens'>
): PlaygroundTokenUsage | null {
  const prompt = typeof metadata.promptTokens === 'number' ? metadata.promptTokens : undefined
  const completion =
    typeof metadata.completionTokens === 'number' ? metadata.completionTokens : undefined
  const totalFromApi = typeof metadata.totalTokens === 'number' ? metadata.totalTokens : undefined

  if (totalFromApi === undefined && prompt === undefined && completion === undefined) {
    return null
  }

  const total =
    totalFromApi ??
    (prompt !== undefined && completion !== undefined ? prompt + completion : undefined)

  if (total === undefined) {
    return null
  }

  return {
    total,
    ...(prompt !== undefined ? { prompt } : {}),
    ...(completion !== undefined ? { completion } : {}),
  }
}
