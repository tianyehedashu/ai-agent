/**
 * 团队凭据摘要目录：id → 显示名（含 system，无密钥）。
 */

import { useMemo } from 'react'

import { useQuery, type QueryClient } from '@tanstack/react-query'

import { gatewayApi, type CredentialSummary } from '@/api/gateway'
import { useGatewayTeamId } from '@/hooks/use-gateway-team-id'

export function credentialSummariesQueryKey(
  teamId: string
): readonly ['gateway', 'credential-summaries', string] {
  return ['gateway', 'credential-summaries', teamId]
}

export interface GatewayCredentialDirectory {
  list: CredentialSummary[]
  byId: Map<string, CredentialSummary>
  isLoading: boolean
}

export function useGatewayCredentialDirectory(): GatewayCredentialDirectory {
  const teamId = useGatewayTeamId()
  const { data: list = [], isLoading } = useQuery({
    queryKey: credentialSummariesQueryKey(teamId),
    queryFn: () => gatewayApi.listCredentialSummaries(teamId),
  })

  const byId = useMemo(() => {
    const m = new Map<string, CredentialSummary>()
    for (const c of list) {
      m.set(c.id, c)
    }
    return m
  }, [list])

  return { list, byId, isLoading }
}

/** 凭据变更后刷新摘要目录 */
export function invalidateCredentialSummariesCache(queryClient: QueryClient): void {
  void queryClient.invalidateQueries({ queryKey: ['gateway', 'credential-summaries'] })
}
