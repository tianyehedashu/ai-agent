/**
 * Actor 维度凭据摘要：跨 membership 团队聚合（与 Playground / 凭据页一致）。
 *
 * 替代按 URL `:teamId` 调用 `listCredentialSummaries`，避免配额中心、日志筛选等
 * 与统一凭据列表数据范围不一致。
 */

import { useMemo } from 'react'

import { useQuery } from '@tanstack/react-query'

import type { PlaygroundCredentialSummary, QuotaRuleLayer } from '@/api/gateway'
import { PLAYGROUND_CREDENTIAL_SUMMARIES_QUERY_KEY } from '@/features/gateway-playground/playground-credential-options'
import { fetchPlaygroundCredentialSummaries } from '@/features/gateway-playground/playground-credential-summaries'
import { useGatewayMembershipTeamIdsKey } from '@/hooks/use-gateway-team-id'
import { useGatewayTeamStore } from '@/stores/gateway-team'

export const ACTOR_CREDENTIAL_SUMMARIES_QUERY_KEY = PLAYGROUND_CREDENTIAL_SUMMARIES_QUERY_KEY

export interface UseActorCredentialSummariesOptions {
  enabled?: boolean
}

export interface ActorCredentialSummariesResult {
  list: readonly PlaygroundCredentialSummary[]
  byId: ReadonlyMap<string, PlaygroundCredentialSummary>
  contextTeamIdByCredentialId: ReadonlyMap<string, string | null>
  isLoading: boolean
  isFetching: boolean
  refetch: () => Promise<unknown>
}

export function useActorCredentialSummaries(
  options?: UseActorCredentialSummariesOptions
): ActorCredentialSummariesResult {
  const membershipTeamIdsKey = useGatewayMembershipTeamIdsKey()
  const enabled = (options?.enabled ?? true) && membershipTeamIdsKey.length > 0

  const query = useQuery({
    queryKey: [...ACTOR_CREDENTIAL_SUMMARIES_QUERY_KEY, membershipTeamIdsKey],
    queryFn: () => fetchPlaygroundCredentialSummaries(useGatewayTeamStore.getState().teams),
    enabled,
    staleTime: 60_000,
  })

  const list = query.data ?? []

  const byId = useMemo(
    (): ReadonlyMap<string, PlaygroundCredentialSummary> => new Map(list.map((c) => [c.id, c])),
    [list]
  )

  const contextTeamIdByCredentialId = useMemo((): ReadonlyMap<string, string | null> => {
    const map = new Map<string, string | null>()
    for (const cred of list) {
      map.set(cred.id, cred.context_team_id ?? null)
    }
    return map
  }, [list])

  return {
    list,
    byId,
    contextTeamIdByCredentialId,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    refetch: query.refetch,
  }
}

export function resolveActorCredentialContextTeamId(
  credentialId: string,
  contextTeamIdByCredentialId: ReadonlyMap<string, string | null>,
  fallbackTeamId: string
): string {
  return contextTeamIdByCredentialId.get(credentialId) ?? fallbackTeamId
}

/** 平台配额凭据维度：成员/Key 均归属 URL 团队，仅展示当前团队凭据。 */
export function filterPlatformQuotaCredentialSummaries(
  creds: readonly PlaygroundCredentialSummary[],
  teamId: string,
  isPlatformAdmin: boolean
): PlaygroundCredentialSummary[] {
  return creds.filter((cred) => {
    if (cred.scope === 'user') return false
    if (cred.scope === 'system') return isPlatformAdmin
    return cred.context_team_id === teamId
  })
}

/** 成员自助配额凭据：platform = 当前团队凭据；upstream = 本人 BYOK。 */
export function filterMemberSelfServiceCredentialSummaries(
  creds: readonly PlaygroundCredentialSummary[],
  teamId: string,
  layer: QuotaRuleLayer = 'platform'
): PlaygroundCredentialSummary[] {
  if (layer === 'upstream') {
    return creds.filter((cred) => cred.scope === 'user' && cred.is_active)
  }
  return creds.filter((cred) => cred.scope === 'team' && cred.context_team_id === teamId)
}

/** 收集 batch 写入涉及的所有 teamId（用于跨团队 upstream 后刷新缓存）。 */
export function collectQuotaBatchTargetTeamIds(
  routeTeamId: string,
  rules: readonly { layer?: string; credential_id?: string | null }[],
  contextTeamIdByCredentialId: ReadonlyMap<string, string | null>
): string[] {
  const teamIds = new Set<string>([routeTeamId])
  for (const rule of rules) {
    if (rule.layer !== 'upstream') continue
    const credId = rule.credential_id
    if (credId === undefined || credId === null) continue
    teamIds.add(
      resolveActorCredentialContextTeamId(credId, contextTeamIdByCredentialId, routeTeamId)
    )
  }
  return [...teamIds]
}

/** 上游配额（厂商凭据额度）：团队/系统凭据（须 admin）或本人 BYOK。 */
export function isUpstreamQuotaCredentialSummary(
  cred: Pick<PlaygroundCredentialSummary, 'scope'>
): boolean {
  return cred.scope === 'user' || cred.scope === 'team' || cred.scope === 'system'
}

/** 上游配额写入可选：含本人 BYOK；团队凭据须 actor 对 context 团队有 admin。 */
export function filterUpstreamQuotaCredentialSummaries(
  creds: readonly PlaygroundCredentialSummary[],
  adminTeamIds: ReadonlySet<string>,
  isPlatformAdmin: boolean
): PlaygroundCredentialSummary[] {
  return creds.filter((cred) => {
    if (!cred.is_active) return false
    if (cred.scope === 'user') return true
    if (cred.scope === 'system') return isPlatformAdmin
    const teamId = cred.context_team_id
    return Boolean(teamId && adminTeamIds.has(teamId))
  })
}
