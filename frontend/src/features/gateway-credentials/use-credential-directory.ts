/**
 * Actor 维度凭据摘要目录：id → 显示名（跨 membership 团队，无密钥）。
 */

import { useMemo } from 'react'

import type { CredentialSummary, PlaygroundCredentialSummary } from '@/api/gateway'
import {
  ACTOR_CREDENTIAL_SUMMARIES_QUERY_KEY,
  useActorCredentialSummaries,
} from '@/features/gateway-credentials/hooks/use-actor-credential-summaries'

import type { QueryClient } from '@tanstack/react-query'

/** @deprecated 凭据目录已改为 actor 聚合；保留 key 前缀供 invalidate 兼容 */
export function credentialSummariesQueryKey(
  _teamId: string
): readonly ['gateway', 'playground', 'credential-summaries', string] {
  return ['gateway', 'playground', 'credential-summaries', _teamId]
}

export interface GatewayCredentialDirectory {
  list: CredentialSummary[]
  byId: Map<string, CredentialSummary>
  contextTeamIdByCredentialId: ReadonlyMap<string, string | null>
  isLoading: boolean
  isFetching: boolean
  refetch: () => Promise<unknown>
}

function toCredentialSummary(cred: PlaygroundCredentialSummary): CredentialSummary {
  return cred
}

export function useGatewayCredentialDirectory(): GatewayCredentialDirectory {
  const { list, contextTeamIdByCredentialId, isLoading, isFetching, refetch } =
    useActorCredentialSummaries()

  const summaries = useMemo(() => list.map(toCredentialSummary), [list])

  const summaryById = useMemo(() => {
    const map = new Map<string, CredentialSummary>()
    for (const cred of summaries) {
      map.set(cred.id, cred)
    }
    return map
  }, [summaries])

  return {
    list: summaries,
    byId: summaryById,
    contextTeamIdByCredentialId,
    isLoading,
    isFetching,
    refetch,
  }
}

/** 凭据变更后刷新 actor 摘要目录 */
export function invalidateCredentialSummariesCache(queryClient: QueryClient): void {
  void queryClient.invalidateQueries({ queryKey: [...ACTOR_CREDENTIAL_SUMMARIES_QUERY_KEY] })
}
