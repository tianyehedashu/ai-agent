/**
 * Playground 模型候选列表：按凭据 scope 分支，避免跨权限合并。
 */

import type { GatewayModel } from '@/api/gateway/models'
import type { PersonalGatewayModel } from '@/api/gateway/my-models'
import { isProxyCallableModel } from '@/features/gateway-models/utils'

import type { ModelCandidate } from './playground-mode-filter'

const MODEL_STATUS_RANK: Record<'success' | 'null' | 'failed', number> = {
  success: 0,
  null: 1,
  failed: 2,
}

function teamRowToCandidate(item: GatewayModel): ModelCandidate | null {
  if (!item.name || !isProxyCallableModel(item)) return null
  return {
    name: item.name,
    scope: 'team',
    status: item.last_test_status,
    capability: item.capability,
    selector_capabilities: item.selector_capabilities,
    model_types: item.model_types,
  }
}

function personalRowToCandidate(item: PersonalGatewayModel): ModelCandidate | null {
  const key = item.name || item.display_name
  if (!key || !isProxyCallableModel(item)) return null
  return {
    name: key,
    scope: 'personal',
    status: item.last_test_status,
    capability: item.capability,
    selector_capabilities: item.selector_capabilities,
    model_types: item.model_types,
  }
}

function sortCandidates(items: ModelCandidate[]): ModelCandidate[] {
  return [...items].sort((a, b) => {
    const ra = MODEL_STATUS_RANK[a.status ?? 'null']
    const rb = MODEL_STATUS_RANK[b.status ?? 'null']
    if (ra !== rb) return ra - rb
    return a.name.localeCompare(b.name)
  })
}

export interface BuildPlaygroundCandidateModelsParams {
  credentialId: string
  isPersonalCredential: boolean
  teamModels: readonly GatewayModel[] | undefined
  myModels: readonly PersonalGatewayModel[] | undefined
}

export function buildPlaygroundCandidateModels({
  credentialId,
  isPersonalCredential,
  teamModels,
  myModels,
}: BuildPlaygroundCandidateModelsParams): ModelCandidate[] {
  const seen = new Map<string, ModelCandidate>()

  if (!credentialId) {
    for (const item of teamModels ?? []) {
      const candidate = teamRowToCandidate(item)
      if (!candidate || seen.has(candidate.name)) continue
      seen.set(candidate.name, candidate)
    }
    for (const item of myModels ?? []) {
      const candidate = personalRowToCandidate(item)
      if (!candidate || seen.has(candidate.name)) continue
      seen.set(candidate.name, candidate)
    }
  } else if (isPersonalCredential) {
    for (const item of myModels ?? []) {
      if (item.credential_id !== credentialId) continue
      const candidate = personalRowToCandidate(item)
      if (!candidate || seen.has(candidate.name)) continue
      seen.set(candidate.name, candidate)
    }
  } else {
    for (const item of teamModels ?? []) {
      const candidate = teamRowToCandidate(item)
      if (!candidate || seen.has(candidate.name)) continue
      seen.set(candidate.name, candidate)
    }
  }

  return sortCandidates(Array.from(seen.values()))
}
