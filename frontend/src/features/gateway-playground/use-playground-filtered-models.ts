/**
 * Playground / 调用指南共用的凭据筛选 + 模型候选查询
 */

import { useCallback, useEffect, useMemo, useState } from 'react'

import { useInfiniteQuery, useQueries, useQueryClient } from '@tanstack/react-query'

import { gatewayApi } from '@/api/gateway'
import { MANAGED_TEAM_MODELS_QUERY_KEY } from '@/features/gateway-models/use-managed-team-models-list'
import {
  GATEWAY_MODELS_STALE_MS,
  GATEWAY_MY_MODELS_ALL_QUERY_KEY,
  playgroundTeamModelsQueryKey,
  resolvePlaygroundTeamRegistryScope,
} from '@/features/gateway-models/utils'
import { MAX_PAGE_SIZE } from '@/lib/pagination'

import {
  isPersonalPlaygroundCredential,
  PLAYGROUND_CREDENTIAL_SUMMARIES_QUERY_KEY,
  resolvePlaygroundContextTeamId,
  usePlaygroundCredentialOptions,
  type PlaygroundCredentialGroups,
  type PlaygroundCredentialOption,
} from './playground-credential-options'
import { buildPlaygroundCandidateModels } from './playground-model-sources'
import {
  filterPlaygroundManagedTeamModels,
  shouldQueryManagedTeamModelsForPlayground,
} from './playground-team-models-query'

import type { ModelCandidate } from './playground-mode-filter'

export interface UsePlaygroundFilteredModelsOptions {
  credentialId?: string
  /** Playground 需要路由列表；Guide 示例区仅需模型候选 */
  includeRoutes?: boolean
}

export interface UsePlaygroundFilteredModelsResult {
  /** Playground 工作区 teamId（personal team，不跟随侧栏） */
  workspaceTeamId: string | null
  /** 当前凭据/模型/Key 请求实际使用的 teamId */
  contextTeamId: string | null
  credentialId: string
  credentialById: Map<string, PlaygroundCredentialOption>
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

  const queryClient = useQueryClient()
  const [modelPickerOpen, setModelPickerOpen] = useState(false)
  const [pendingModelNames, setPendingModelNames] = useState<Set<string>>(() => new Set())

  const {
    grouped: credentialGroups,
    byId: credentialById,
    workspaceTeamId,
    isLoading: credentialsLoading,
    isFetching: credentialsFetching,
    isEmpty: credentialsEmpty,
  } = usePlaygroundCredentialOptions()

  const contextTeamId = useMemo(
    () => resolvePlaygroundContextTeamId(credentialId, credentialById, workspaceTeamId),
    [credentialId, credentialById, workspaceTeamId]
  )

  const isPersonalCredential = isPersonalPlaygroundCredential(credentialById, credentialId)
  const teamCredentialFilter = credentialId && !isPersonalCredential ? credentialId : ''
  const teamRegistryScope = resolvePlaygroundTeamRegistryScope(teamCredentialFilter)
  const useManagedTeamModelsQuery = shouldQueryManagedTeamModelsForPlayground(
    teamCredentialFilter,
    isPersonalCredential
  )
  const includeTeamModels =
    useManagedTeamModelsQuery ||
    (Boolean(contextTeamId) && (!credentialId || !isPersonalCredential))
  const includeMyModels = !credentialId || isPersonalCredential
  const includeRoutes =
    fetchRoutes && Boolean(contextTeamId) && !(credentialId && isPersonalCredential)

  const teamModelsQuery = useInfiniteQuery({
    queryKey: useManagedTeamModelsQuery
      ? [
          ...MANAGED_TEAM_MODELS_QUERY_KEY,
          'playground',
          teamCredentialFilter,
          contextTeamId ?? '',
          'infinite',
        ]
      : contextTeamId
        ? [...playgroundTeamModelsQueryKey(contextTeamId, teamCredentialFilter), 'infinite']
        : ['gateway', 'models', 'requestable', 'none'],
    queryFn: ({ pageParam }) => {
      if (useManagedTeamModelsQuery) {
        return gatewayApi.listManagedTeamModels({
          credential_id: teamCredentialFilter,
          page: pageParam,
          page_size: MAX_PAGE_SIZE,
        })
      }
      if (!contextTeamId) return Promise.reject(new Error('未选择团队'))
      return gatewayApi.listModels(contextTeamId, {
        registry_scope: teamRegistryScope,
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
        queryKey: ['gateway', 'routes', contextTeamId, credentialId],
        queryFn: () => {
          if (!contextTeamId) return Promise.reject(new Error('未选择团队'))
          return gatewayApi.listRoutes(contextTeamId)
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

  const teamModels = useMemo(() => {
    const items = teamData?.pages.flatMap((page) => page.items) ?? []
    if (!useManagedTeamModelsQuery) return items
    return filterPlaygroundManagedTeamModels(items, contextTeamId)
  }, [teamData, useManagedTeamModelsQuery, contextTeamId])
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
    setPendingModelNames((prev) => {
      if (prev.has(trimmed)) return prev
      const next = new Set(prev)
      next.add(trimmed)
      return next
    })
  }, [])

  // 仅对 ensureModelNameLoaded 登记的名字翻页（选中模型/路由时由 UI 触发，避免 mount 拉全量路由主模型）
  useEffect(() => {
    const unresolved = [...pendingModelNames].filter((name) => !candidateNames.has(name))
    if (unresolved.length === 0) {
      if (pendingModelNames.size > 0) {
        setPendingModelNames(new Set())
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
    setPendingModelNames(new Set())
  }, [
    pendingModelNames,
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
    teamModelsFetching || myModelsFetching || routesQuery.isFetching || credentialsFetching

  const refreshAll = useCallback((): void => {
    void Promise.all([
      refetchTeamModels(),
      refetchMyModels(),
      routesQuery.refetch(),
      queryClient.invalidateQueries({ queryKey: [...PLAYGROUND_CREDENTIAL_SUMMARIES_QUERY_KEY] }),
      queryClient.invalidateQueries({ queryKey: [...MANAGED_TEAM_MODELS_QUERY_KEY] }),
    ])
  }, [queryClient, refetchMyModels, refetchTeamModels, routesQuery])

  return {
    workspaceTeamId,
    contextTeamId,
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
