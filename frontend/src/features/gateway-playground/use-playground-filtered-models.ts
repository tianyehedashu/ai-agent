/**
 * Playground / 调用指南共用的凭据筛选 + 模型候选查询
 */

import { useCallback, useEffect, useMemo, useState } from 'react'

import { useInfiniteQuery, useQueries, useQuery, useQueryClient } from '@tanstack/react-query'

import { gatewayApi } from '@/api/gateway'
import { MANAGED_TEAM_MODELS_QUERY_KEY } from '@/features/gateway-models/use-managed-team-models-list'
import {
  GATEWAY_MODELS_STALE_MS,
  GATEWAY_MY_MODELS_ALL_QUERY_KEY,
  playgroundTeamModelsQueryKey,
  resolvePlaygroundTeamRegistryScope,
} from '@/features/gateway-models/utils'
import { useGatewayTeamRecord } from '@/hooks/use-gateway-team-id'
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
import { fetchPlaygroundProxyModels } from './playground-proxy-models'
import { isPersonalGatewayTeam, resolvePlaygroundProxyTeamId } from './playground-proxy-team'
import {
  mergePlaygroundRouteRows,
  resolvePlaygroundRouteFetchPolicy,
} from './playground-route-sources'
import {
  filterPlaygroundManagedTeamModels,
  shouldQueryManagedTeamModelsForPlayground,
} from './playground-team-models-query'

import type { ModelCandidate } from './playground-mode-filter'
import type { PlaygroundRouteRow } from './playground-route-sources'

export interface UsePlaygroundFilteredModelsOptions {
  credentialId?: string
  /** Playground 需要路由列表；Guide 示例区仅需模型候选 */
  includeRoutes?: boolean
  /** 已选虚拟 Key 的 team_id；与后端 Bearer 鉴权团队对齐，避免模型列表与 Key 不一致 */
  proxyTeamId?: string | null
  /** multi-grant vkey 已 reveal 明文时，经 GET /v1/models 拉合并 callable 列表 */
  proxyVkeyPlain?: string | null
  proxyVkeyBaseUrl?: string | null
  proxyVkeyId?: string | null
  multiGrantVkey?: boolean
}

export interface UsePlaygroundFilteredModelsResult {
  /** Playground 工作区 teamId（personal team，不跟随侧栏） */
  workspaceTeamId: string | null
  /** 凭据筛选推导的团队（未选 Key 时用于拉模型） */
  contextTeamId: string | null
  /** 代理实际解析团队（Key 优先） */
  proxyTeamId: string | null
  /** proxyTeamId 是否为个人工作区（下拉分组用） */
  isPersonalProxyTeam: boolean
  credentialId: string
  credentialById: Map<string, PlaygroundCredentialOption>
  credentialsLoading: boolean
  credentialsEmpty: boolean
  credentialGroups: PlaygroundCredentialGroups
  isPersonalCredential: boolean
  includeTeamModels: boolean
  includeMyModels: boolean
  includeRoutes: boolean
  includeOwnedRoutes: boolean
  includeSharedRoutes: boolean
  candidateModels: ModelCandidate[]
  routes: PlaygroundRouteRow[] | undefined
  modelsLoading: boolean
  teamModelsLoaded: boolean
  myModelsLoaded: boolean
  /** 模型下拉打开时继续翻页；关闭后仅保留已加载页 */
  onModelPickerOpenChange: (open: boolean) => void
  /** 选中模型名不在已加载页时，按需拉取下一页直至命中或耗尽 */
  ensureModelNameLoaded: (modelName: string) => void
  isRefreshing: boolean
  refreshAll: () => void
  /** multi-grant vkey 使用代理 /v1/models 列表 */
  usingProxyModelList: boolean
  proxyModelsLoading: boolean
  proxyModelsError: Error | null
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
  const selectedKeyTeamId = options.proxyTeamId ?? null
  const proxyVkeyPlain = options.proxyVkeyPlain?.trim() ?? ''
  const proxyVkeyBaseUrl = options.proxyVkeyBaseUrl?.trim() ?? ''
  const proxyVkeyId = options.proxyVkeyId ?? null
  const multiGrantVkey = options.multiGrantVkey ?? false
  const usingProxyModelList =
    multiGrantVkey && proxyVkeyPlain.length > 0 && proxyVkeyBaseUrl.length > 0

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

  const proxyTeamId = useMemo(
    () =>
      resolvePlaygroundProxyTeamId(
        selectedKeyTeamId ? { team_id: selectedKeyTeamId } : null,
        credentialId,
        credentialById,
        workspaceTeamId
      ),
    [selectedKeyTeamId, credentialId, credentialById, workspaceTeamId]
  )

  const isPersonalCredential = isPersonalPlaygroundCredential(credentialById, credentialId)
  const proxyTeam = useGatewayTeamRecord(proxyTeamId)
  const isPersonalProxyTeam = isPersonalGatewayTeam(proxyTeam)
  const teamCredentialFilter = credentialId && !isPersonalCredential ? credentialId : ''
  const teamRegistryScope = resolvePlaygroundTeamRegistryScope(teamCredentialFilter)
  const useManagedTeamModelsQuery = shouldQueryManagedTeamModelsForPlayground(
    teamCredentialFilter,
    isPersonalCredential
  )
  const includeTeamModels =
    !usingProxyModelList &&
    (useManagedTeamModelsQuery ||
      (Boolean(proxyTeamId) && (!credentialId || !isPersonalCredential)))
  const includeMyModels =
    !usingProxyModelList &&
    (!credentialId || isPersonalCredential) &&
    (!selectedKeyTeamId || isPersonalProxyTeam)
  const routeFetchPolicy = resolvePlaygroundRouteFetchPolicy({
    fetchRoutes,
    proxyTeamId,
    isPersonalProxyTeam,
    credentialId,
    isPersonalCredential,
    usingProxyModelList,
  })
  const { includeOwnedRoutes, includeSharedRoutes } = routeFetchPolicy
  const includeRoutes = includeOwnedRoutes || includeSharedRoutes

  const proxyModelsQuery = useQuery({
    queryKey: ['gateway', 'playground', 'proxy-models', proxyVkeyId, proxyVkeyBaseUrl] as const,
    queryFn: () => fetchPlaygroundProxyModels(proxyVkeyBaseUrl, proxyVkeyPlain),
    enabled: usingProxyModelList,
    staleTime: GATEWAY_MODELS_STALE_MS,
  })

  const teamModelsQuery = useInfiniteQuery({
    queryKey: useManagedTeamModelsQuery
      ? [
          ...MANAGED_TEAM_MODELS_QUERY_KEY,
          'playground',
          teamCredentialFilter,
          proxyTeamId ?? '',
          'infinite',
        ]
      : proxyTeamId
        ? [...playgroundTeamModelsQueryKey(proxyTeamId, teamCredentialFilter), 'infinite']
        : ['gateway', 'models', 'requestable', 'none'],
    queryFn: ({ pageParam }) => {
      if (useManagedTeamModelsQuery) {
        return gatewayApi.listManagedTeamModels({
          credential_id: teamCredentialFilter,
          page: pageParam,
          page_size: MAX_PAGE_SIZE,
        })
      }
      if (!proxyTeamId) return Promise.reject(new Error('未选择团队'))
      return gatewayApi.listModels(proxyTeamId, {
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

  const [ownedRoutesQuery, sharedRoutesQuery] = useQueries({
    queries: [
      {
        queryKey: ['gateway', 'routes', proxyTeamId, credentialId] as const,
        queryFn: () => {
          if (!proxyTeamId) return Promise.reject(new Error('未选择团队'))
          return gatewayApi.listRoutes(proxyTeamId)
        },
        enabled: includeOwnedRoutes,
        staleTime: GATEWAY_MODELS_STALE_MS,
      },
      {
        queryKey: ['gateway', 'shared-routes', proxyTeamId] as const,
        queryFn: () => {
          if (!proxyTeamId) return Promise.reject(new Error('未选择团队'))
          return gatewayApi.listSharedRoutes(proxyTeamId)
        },
        enabled: includeSharedRoutes,
        staleTime: GATEWAY_MODELS_STALE_MS,
      },
    ],
  })

  const playgroundRoutes = useMemo(
    () => mergePlaygroundRouteRows(ownedRoutesQuery.data, sharedRoutesQuery.data),
    [ownedRoutesQuery.data, sharedRoutesQuery.data]
  )

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
    refetch: refetchProxyModels,
    isSuccess: proxyModelsSuccess,
    isError: proxyModelsIsError,
  } = proxyModelsQuery

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
    return filterPlaygroundManagedTeamModels(items, proxyTeamId)
  }, [teamData, useManagedTeamModelsQuery, proxyTeamId])
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

  const candidateModels = useMemo<ModelCandidate[]>(() => {
    if (usingProxyModelList) {
      return proxyModelsQuery.data ?? []
    }
    return buildPlaygroundCandidateModels({
      credentialId,
      isPersonalCredential,
      teamModels,
      myModels,
    })
  }, [
    usingProxyModelList,
    proxyModelsQuery.data,
    credentialId,
    isPersonalCredential,
    teamModels,
    myModels,
  ])

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

  const proxyModelsLoading = usingProxyModelList && proxyModelsQuery.isLoading
  const proxyModelsError = proxyModelsQuery.error instanceof Error ? proxyModelsQuery.error : null

  const proxyModelsSettled =
    !usingProxyModelList || (!proxyModelsLoading && (proxyModelsSuccess || proxyModelsIsError))

  const teamModelsLoaded = usingProxyModelList
    ? proxyModelsSettled && proxyModelsSuccess
    : !includeTeamModels || teamModelsSuccess

  const myModelsLoaded = usingProxyModelList ? true : !includeMyModels || myModelsSuccess

  const routesLoading =
    (includeOwnedRoutes && ownedRoutesQuery.isLoading) ||
    (includeSharedRoutes && sharedRoutesQuery.isLoading)
  const routesFetching =
    (includeOwnedRoutes && ownedRoutesQuery.isFetching) ||
    (includeSharedRoutes && sharedRoutesQuery.isFetching)

  const modelsLoading =
    teamModelsLoading ||
    myModelsLoading ||
    routesLoading ||
    credentialsLoading ||
    proxyModelsLoading

  const isRefreshing =
    teamModelsFetching ||
    myModelsFetching ||
    routesFetching ||
    credentialsFetching ||
    (usingProxyModelList && proxyModelsQuery.isFetching)

  const refreshAll = useCallback((): void => {
    void Promise.all([
      usingProxyModelList ? refetchProxyModels() : refetchTeamModels(),
      usingProxyModelList ? Promise.resolve() : refetchMyModels(),
      includeOwnedRoutes ? ownedRoutesQuery.refetch() : Promise.resolve(),
      includeSharedRoutes ? sharedRoutesQuery.refetch() : Promise.resolve(),
      queryClient.invalidateQueries({ queryKey: [...PLAYGROUND_CREDENTIAL_SUMMARIES_QUERY_KEY] }),
      queryClient.invalidateQueries({ queryKey: [...MANAGED_TEAM_MODELS_QUERY_KEY] }),
    ])
  }, [
    queryClient,
    refetchMyModels,
    refetchTeamModels,
    refetchProxyModels,
    ownedRoutesQuery,
    sharedRoutesQuery,
    includeOwnedRoutes,
    includeSharedRoutes,
    usingProxyModelList,
  ])

  return {
    workspaceTeamId,
    contextTeamId,
    proxyTeamId,
    isPersonalProxyTeam,
    credentialId,
    credentialById,
    credentialsLoading,
    credentialsEmpty,
    credentialGroups,
    isPersonalCredential,
    includeTeamModels,
    includeMyModels,
    includeRoutes,
    includeOwnedRoutes,
    includeSharedRoutes,
    candidateModels,
    routes: includeRoutes ? playgroundRoutes : undefined,
    modelsLoading,
    teamModelsLoaded,
    myModelsLoaded,
    onModelPickerOpenChange,
    ensureModelNameLoaded,
    isRefreshing,
    refreshAll,
    usingProxyModelList,
    proxyModelsLoading,
    proxyModelsError,
  }
}
