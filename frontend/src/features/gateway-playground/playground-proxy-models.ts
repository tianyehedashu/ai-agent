/**
 * Playground / 调用指南：经 Bearer vkey 拉取 GET /v1/models（multi-grant 合并列表）
 */

import { messageFromApiErrorBody } from '@/lib/fastapi-error-detail'
import type { ModelTestStatus } from '@/types/user-model'

import type { ModelCandidate } from './playground-mode-filter'

/** OpenAI 兼容 GET /v1/models 单条（子集） */
export interface ProxyModelListItem {
  id: string
  capability?: string
  model_types?: string[]
  owned_by?: string
  gateway?: {
    callable?: boolean
    connectivity_status?: string
    selector_capabilities?: Record<string, unknown>
    registry_name?: string
    team_slug?: string | null
  }
}

export interface ProxyModelsListResponse {
  data?: ProxyModelListItem[]
}

function connectivityToTestStatus(connectivity: string | undefined): ModelTestStatus {
  if (connectivity === 'success') return 'success'
  if (connectivity === 'failed') return 'failed'
  return null
}

export function proxyModelItemToCandidate(item: ProxyModelListItem): ModelCandidate | null {
  const gw = item.gateway
  if (gw?.callable === false) return null
  const name = item.id.trim()
  if (!name) return null
  return {
    name,
    scope: 'team',
    status: connectivityToTestStatus(gw?.connectivity_status),
    capability: item.capability ?? 'chat',
    provider: item.owned_by ?? '',
    teamSlug: gw?.team_slug ?? null,
    selector_capabilities: gw?.selector_capabilities,
    model_types: item.model_types,
  }
}

export function parseProxyModelsToCandidates(
  items: readonly ProxyModelListItem[] | undefined
): ModelCandidate[] {
  const seen = new Map<string, ModelCandidate>()
  for (const item of items ?? []) {
    const candidate = proxyModelItemToCandidate(item)
    if (!candidate || seen.has(candidate.name)) continue
    seen.set(candidate.name, candidate)
  }
  return [...seen.values()].sort((a, b) => a.name.localeCompare(b.name))
}

export async function fetchPlaygroundProxyModels(
  baseUrl: string,
  plainKey: string
): Promise<ModelCandidate[]> {
  const normalizedBase = baseUrl.replace(/\/$/, '')
  const res = await fetch(`${normalizedBase}/models`, {
    headers: { Authorization: `Bearer ${plainKey}` },
  })
  if (!res.ok) {
    const raw = await res.text().catch(() => '')
    let body: unknown = raw
    try {
      body = raw ? (JSON.parse(raw) as unknown) : raw
    } catch {
      body = raw
    }
    throw new Error(messageFromApiErrorBody(body, `GET /models failed (${String(res.status)})`))
  }
  const json = (await res.json()) as ProxyModelsListResponse
  return parseProxyModelsToCandidates(json.data)
}

export function isMultiGrantVirtualKey(grantedTeamIds: readonly string[] | undefined): boolean {
  return (grantedTeamIds?.length ?? 1) > 1
}
