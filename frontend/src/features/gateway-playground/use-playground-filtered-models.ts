/**
 * Playground / 调用指南共用的凭据筛选 + 模型候选查询
 */

import { useCallback, useEffect, useMemo, useState } from 'react'

import { useInfiniteQuery, useQueries, useQueryClient } from '@tanstack/react-query'

import type { CredentialSummary } from '@/api/gateway'
import { gatewayApi } from '@/api/gateway'
import {
  GATEWAY_MODELS_STALE_MS,
  GATEWAY_MY_MODELS_ALL_QUERY_KEY,
  playgroundTeamModelsQueryKey,
  resolvePlaygroundTeamRegistryScope,
} from '@/features/gateway-models/utils'
import { useResolvedGatewayTeamId } from '@/hooks/use-gateway-team-id'
import { MAX_PAGE_SIZE } from '@/lib/pagination'

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
  /** 模型下拉打开时继续翻页；关闭后仅保留已加载页 */
  onModelPickerOpenChange: (open: boolean) => void
  /** 选中模型名不在已加载页时，按需拉取下一页直至命中或耗尽 */
  ensureModelNameLoaded: (modelName: string) => void
  isRefreshing: boolean
  refreshAll: () => void
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
  const queryClient = useQueryClient()
  const [modelPickerOpen, setModelPickerOpen] = useState(false)
  const [pendingModelName, setPendingModelName] = useState<string | null>(null)

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

  const teamModelsQuery = useInfiniteQuery({
    queryKey: teamId
      ? [...playgroundTeamModelsQueryKey(teamId, teamCredentialFilter), 'infinite']
      : ['gateway', 'models', 'requestable', 'none'],
    queryFn: ({ pageParam }) => {
      if (!teamId) return Promise.reject(new Error('未选择团队'))
      return gatewayApi.listModels(teamId, {
        registry_scope: teamRegistryScope,
        ...(teamCredentialFilter ? { credential_id: teamCredentialFilter } : {}),
        page: pageParam,
        page_size: MAX_PAGE_SIZE,
      })
    },
    initialPageParam: 1,
    getNextPageParam: (lastPage) => (lastPage.has_next ? lastPage.page + 1 : undefined),
    enabled: includeTeamModels,
    staleTime: GATEWAY_MODELS_STALE_MS,
  })

  const myModelsQuery = useInfiniteQuery({
    queryKey: [...GATEWAY_MY_MODELS_ALL_QUERY_KEY, 'infinite'],
    queryFn: ({ pageParam }) =>
      gatewayApi.listMyModels({ page: pageParam, page_size: MAX_PAGE_SIZE }),
    initialPageParam: 1,
    getNextPageParam: (lastPage) => (lastPage.has_next ? lastPage.page + 1 : undefined),
    enabled: includeMyModels,
    staleTime: GATEWAY_MODELS_STALE_MS,
  })

  const [routesQuery] = useQueries({
    queries: [
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

  const {
    fetchNextPage: fetchNextTeamPage,
    hasNextPage: teamHasNextPage,
    isFetchingNextPage: isFetchingNextTeamPage,
    isFetching: teamModelsFetching,
    refetch: refetchTeamModels,
    data: teamData,
    isLoading: teamModelsLoading,
    isSuccess: teamModelsSuccess,
  } = teamModelsQuery

  const {
    fetchNextPage: fetchNextMyPage,
    hasNextPage: myHasNextPage,
    isFetchingNextPage: isFetchingNextMyPage,
    isFetching: myModelsFetching,
    refetch: refetchMyModels,
    data: myData,
    isLoading: myModelsLoading,
    isSuccess: myModelsSuccess,
  } = myModelsQuery

  const teamModels = useMemo(() => teamData?.pages.flatMap((page) => page.items) ?? [], [teamData])
  const myModels = useMemo(() => myData?.pages.flatMap((page) => page.items) ?? [], [myData])

  const shouldLoadMoreTeam = includeTeamModels && teamHasNextPage && !isFetchingNextTeamPage
  const shouldLoadMoreMy = includeMyModels && myHasNextPage && !isFetchingNextMyPage

  // 下拉打开时串行翻页，避免 mount 拉全量
  useEffect(() => {
    if (!modelPickerOpen) return
    if (shouldLoadMoreTeam) {
      void fetchNextTeamPage()
      return
    }
    if (shouldLoadMoreMy) {
      void fetchNextMyPage()
    }
  }, [
    modelPickerOpen,
    shouldLoadMoreTeam,
    shouldLoadMoreMy,
    fetchNextTeamPage,
    fetchNextMyPage,
    teamData?.pages.length,
    myData?.pages.length,
  ])

  const candidateModels = useMemo<ModelCandidate[]>(
    () =>
      buildPlaygroundCandidateModels({
        credentialId,
        isPersonalCredential,
        teamModels,
        myModels,
      }),
    [credentialId, isPersonalCredential, teamModels, myModels]
  )

  const candidateNames = useMemo(
    () => new Set(candidateModels.map((m) => m.name)),
    [candidateModels]
  )

  const ensureModelNameLoaded = useCallback((modelName: string): void => {
    const trimmed = modelName.trim()
    if (!trimmed) return
    setPendingModelName(trimmed)
  }, [])

  // 选中模型可能在后续页：按需翻页直至命中或耗尽
  useEffect(() => {
    if (!pendingModelName || candidateNames.has(pendingModelName)) {
      if (pendingModelName && candidateNames.has(pendingModelName)) {
        setPendingModelName(null)
      }
      return
    }
    if (shouldLoadMoreTeam) {
      void fetchNextTeamPage()
      return
    }
    if (shouldLoadMoreMy) {
      void fetchNextMyPage()
      return
    }
    setPendingModelName(null)
  }, [
    pendingModelName,
    candidateNames,
    shouldLoadMoreTeam,
    shouldLoadMoreMy,
    fetchNextTeamPage,
    fetchNextMyPage,
    teamData?.pages.length,
    myData?.pages.length,
  ])

  const onModelPickerOpenChange = useCallback((open: boolean): void => {
    setModelPickerOpen(open)
  }, [])

  const modelsLoading =
    teamModelsLoading || myModelsLoading || routesQuery.isLoading || credentialsLoading

  const isRefreshing =
    teamModelsFetching || myModelsFetching || routesQuery.isFetching || credentialsLoading

  const refreshAll = useCallback((): void => {
    void Promise.all([
      refetchTeamModels(),
      refetchMyModels(),
      routesQuery.refetch(),
      queryClient.invalidateQueries({ queryKey: ['gateway', 'credential-summaries'] }),
      queryClient.invalidateQueries({ queryKey: ['gateway', 'my-credentials'] }),
    ])
  }, [queryClient, refetchMyModels, refetchTeamModels, routesQuery])

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
    teamModelsLoaded: !includeTeamModels || teamModelsSuccess,
    myModelsLoaded: !includeMyModels || myModelsSuccess,
    onModelPickerOpenChange,
    ensureModelNameLoaded,
    isRefreshing,
    refreshAll,
  }
}
