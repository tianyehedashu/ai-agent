/**
 * Playground 代理调用团队上下文：与后端 vkey.team_id 解析对齐。
 */

import type { VirtualKey } from '@/api/gateway'
import type { GatewayTeam } from '@/stores/gateway-team'

import {
  resolvePlaygroundContextTeamId,
  type PlaygroundCredentialOption,
} from './playground-credential-options'

import type { ModelCandidate } from './playground-mode-filter'

export function isPersonalGatewayTeam(team: Pick<GatewayTeam, 'kind'> | null | undefined): boolean {
  return team?.kind === 'personal'
}

/**
 * 下拉分组（与 Key 绑定团队对齐）：
 * - 个人工作区 Key → 仅「工作区模型」，不含协作团队分组
 * - 协作团队 Key → 仅「团队模型」，不含 BYOK 个人模型
 */
export function splitPlaygroundModelCandidatesForDisplay(
  models: readonly ModelCandidate[],
  isPersonalProxyTeam: boolean
): { teamCandidates: ModelCandidate[]; personalCandidates: ModelCandidate[] } {
  const teamCandidates: ModelCandidate[] = []
  const personalCandidates: ModelCandidate[] = []
  for (const m of models) {
    if (isPersonalProxyTeam) {
      personalCandidates.push(m)
      continue
    }
    if (m.scope === 'team') {
      teamCandidates.push(m)
    }
  }
  return { teamCandidates, personalCandidates }
}

/** 实际代理解析使用的团队：已选 Key 优先，否则凭据/工作区上下文。 */
export function resolvePlaygroundProxyTeamId(
  selectedKey: Pick<VirtualKey, 'team_id'> | null | undefined,
  credentialId: string,
  credentialById: ReadonlyMap<string, PlaygroundCredentialOption>,
  workspaceTeamId: string | null
): string | null {
  if (selectedKey?.team_id) return selectedKey.team_id
  return resolvePlaygroundContextTeamId(credentialId, credentialById, workspaceTeamId)
}

/** Key 白名单过滤（模型名 / 虚拟路由名）；空列表表示不限制。 */
export function filterPlaygroundNamesForVirtualKey<T extends { name: string }>(
  items: readonly T[],
  allowedModels: readonly string[] | undefined
): T[] {
  if (!allowedModels || allowedModels.length === 0) return [...items]
  const allowed = new Set(allowedModels)
  return items.filter((item) => allowed.has(item.name))
}

export function filterPlaygroundCandidatesForVirtualKey(
  candidates: readonly ModelCandidate[],
  allowedModels: readonly string[] | undefined
): ModelCandidate[] {
  return filterPlaygroundNamesForVirtualKey(candidates, allowedModels)
}
