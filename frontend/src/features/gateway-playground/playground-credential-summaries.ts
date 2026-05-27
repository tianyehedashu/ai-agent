/**
 * Playground 凭据摘要拉取（聚合 API + 旧端点回退）
 */

import { ApiError } from '@/api/errors'
import {
  gatewayApi,
  type CredentialSummary,
  type PlaygroundCredentialSummary,
  type ProviderCredential,
} from '@/api/gateway'
import type { GatewayTeam } from '@/stores/gateway-team'

export function personalCredentialToPlaygroundSummary(
  c: ProviderCredential,
  personalTeamId: string | null
): PlaygroundCredentialSummary {
  return {
    id: c.id,
    provider: c.provider,
    name: c.name,
    scope: 'user',
    is_active: c.is_active,
    is_config_managed: c.is_config_managed ?? false,
    context_team_id: personalTeamId,
  }
}

function teamSummaryToPlayground(
  summary: CredentialSummary,
  teamId: string
): PlaygroundCredentialSummary {
  return {
    ...summary,
    context_team_id: teamId,
  }
}

/** 后端未部署聚合端点时的客户端回退（语义须与 playground_credential_reads.py 一致）。
 * TODO: 全环境 playground API 可用后删除此回退及 fetchPlaygroundCredentialSummaries 中的 404 分支。
 */
export async function listPlaygroundCredentialSummariesFallback(
  teams: readonly GatewayTeam[]
): Promise<PlaygroundCredentialSummary[]> {
  const personalTeamId = teams.find((t) => t.kind === 'personal')?.id ?? null
  const byId = new Map<string, PlaygroundCredentialSummary>()

  for (const c of await gatewayApi.listMyCredentials()) {
    if (!c.is_active) continue
    byId.set(c.id, personalCredentialToPlaygroundSummary(c, personalTeamId))
  }

  await Promise.all(
    teams.map(async (team) => {
      const rows = await gatewayApi.listCredentialSummaries(team.id)
      for (const row of rows) {
        if (!row.is_active) continue
        if (row.scope === 'user' || byId.has(row.id)) continue
        byId.set(row.id, teamSummaryToPlayground(row, team.id))
      }
    })
  )

  return Array.from(byId.values())
}

export async function fetchPlaygroundCredentialSummaries(
  teams: readonly GatewayTeam[]
): Promise<PlaygroundCredentialSummary[]> {
  try {
    return await gatewayApi.listPlaygroundCredentialSummaries()
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return listPlaygroundCredentialSummariesFallback(teams)
    }
    throw error
  }
}

/** 解析虚拟 Key 列表应拉取哪些团队 */
export function resolvePlaygroundVirtualKeyTeamIds(
  credentialId: string,
  byId: ReadonlyMap<string, PlaygroundCredentialSummary>,
  workspaceTeamId: string | null,
  membershipTeamIds: readonly string[]
): string[] {
  if (!credentialId) return [...membershipTeamIds]
  const cred = byId.get(credentialId)
  if (!cred || cred.scope === 'user') {
    return workspaceTeamId ? [workspaceTeamId] : []
  }
  const ctx = cred.context_team_id ?? workspaceTeamId
  return ctx ? [ctx] : []
}
