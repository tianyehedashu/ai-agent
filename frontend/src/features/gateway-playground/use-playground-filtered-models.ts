/**
 * Playground / 调用指南共用的凭据筛选 + 模型候选查询
 */

import { useMemo } from 'react'

import { useQueries } from '@tanstack/react-query'

import type { CredentialSummary } from '@/api/gateway'
import { gatewayApi } from '@/api/gateway'
import {
  GATEWAY_MODELS_STALE_MS,
  GATEWAY_MY_MODELS_ALL_QUERY_KEY,
  playgroundTeamModelsQueryKey,
  resolvePlaygroundTeamRegistryScope,
} from '@/features/gateway-models/utils'
import { useResolvedGatewayTeamId } from '@/hooks/use-gateway-team-id'

import {
  isPersonalPlaygroundCredential,
  usePlaygroundCredentialOptions,
  type PlaygroundCredentialGroups,
} from './playground-credential-options'
import { buildPlaygroundCandidateModels } from './playground-model-sources'

import type { ModelCandidate } from './playground-mode-filter'

export interface UsePlaygroundFilteredModelsOptions {
  credentialId?: string
  /** Playground 需要路由列表；Guide 示例区仅需模型候选 */
  includeRoutes?: boolean
}

export interface UsePlaygroundFilteredModelsResult {
  teamId: string | null
  credentialId: string
  credentialById: Map<string, CredentialSummary>
  credentialsLoading: boolean
  credentialsEmpty: boolean
  credentialGroups: PlaygroundCredentialGroups
  isPersonalCredential: boolean
  includeTeamModels: boolean
  includeMyModels: boolean
  includeRoutes: boolean
  candidateModels: ModelCandidate[]
  routes: Awaited<ReturnType<typeof gatewayApi.listRoutes>> | undefined
  modelsLoading: boolean
  teamModelsLoaded: boolean
  myModelsLoaded: boolean
}

/** 父级注入 PlaygroundCard 的快照，避免同页重复跑 hook */
export type PlaygroundModelsSnapshot = UsePlaygroundFilteredModelsResult

/** @deprecated 使用 ``PlaygroundModelsSnapshot`` */
export type PlaygroundFilteredModelsSnapshot = PlaygroundModelsSnapshot

export function usePlaygroundFilteredModels(
  options: UsePlaygroundFilteredModelsOptions = {}
): UsePlaygroundFilteredModelsResult {
  const credentialId = options.credentialId ?? ''
  const fetchRoutes = options.includeRoutes ?? false

  const teamId = useResolvedGatewayTeamId()

  const {
    grouped: credentialGroups,
    byId: credentialById,
    isLoading: credentialsLoading,
    isEmpty: credentialsEmpty,
  } = usePlaygroundCredentialOptions(credentialId)

  const isPersonalCredential = isPersonalPlaygroundCredential(credentialById, credentialId)
  const teamCredentialFilter = credentialId && !isPersonalCredential ? credentialId : ''
  const teamRegistryScope = resolvePlaygroundTeamRegistryScope(teamCredentialFilter)
  const includeTeamModels = Boolean(teamId) && (!credentialId || !isPersonalCredential)
  const includeMyModels = !credentialId || isPersonalCredential
  const includeRoutes = fetchRoutes && Boolean(teamId) && !(credentialId && isPersonalCredential)

  const [teamModelsQuery, myModelsQuery, routesQuery] = useQueries({
    queries: [
      {
        queryKey: teamId
          ? playgroundTeamModelsQueryKey(teamId, teamCredentialFilter)
          : ['gateway', 'models', 'requestable', 'none'],
        queryFn: () => {
          if (!teamId) return Promise.reject(new Error('未选择团队'))
          return gatewayApi.listModels(teamId, {
            registry_scope: teamRegistryScope,
            ...(teamCredentialFilter ? { credential_id: teamCredentialFilter } : {}),
          })
        },
        enabled: includeTeamModels,
        staleTime: GATEWAY_MODELS_STALE_MS,
      },
      {
        queryKey: GATEWAY_MY_MODELS_ALL_QUERY_KEY,
        queryFn: () => gatewayApi.listMyModels(),
        enabled: includeMyModels,
        staleTime: GATEWAY_MODELS_STALE_MS,
      },
      {
        queryKey: ['gateway', 'routes', teamId, credentialId],
        queryFn: () => {
          if (!teamId) return Promise.reject(new Error('未选择团队'))
          return gatewayApi.listRoutes(teamId)
        },
        enabled: includeRoutes,
        staleTime: GATEWAY_MODELS_STALE_MS,
      },
    ],
  })

  const candidateModels = useMemo<ModelCandidate[]>(
    () =>
      buildPlaygroundCandidateModels({
        credentialId,
        isPersonalCredential,
        teamModels: teamModelsQuery.data,
        myModels: myModelsQuery.data,
      }),
    [credentialId, isPersonalCredential, teamModelsQuery.data, myModelsQuery.data]
  )

  const modelsLoading =
    teamModelsQuery.isLoading ||
    myModelsQuery.isLoading ||
    routesQuery.isLoading ||
    credentialsLoading

  return {
    teamId,
    credentialId,
    credentialById,
    credentialsLoading,
    credentialsEmpty,
    credentialGroups,
    isPersonalCredential,
    includeTeamModels,
    includeMyModels,
    includeRoutes,
    candidateModels,
    routes: routesQuery.data,
    modelsLoading,
    teamModelsLoaded: !includeTeamModels || teamModelsQuery.isSuccess,
    myModelsLoaded: !includeMyModels || myModelsQuery.isSuccess,
  }
}
