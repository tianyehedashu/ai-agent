import { useCallback, useEffect, useMemo, useState } from 'react'

import { useInfiniteQuery } from '@tanstack/react-query'

import { gatewayApi } from '@/api/gateway'
import type { GatewayModelListQuery, GatewayModel } from '@/api/gateway/models'
import type { PersonalModelListQuery, PersonalGatewayModel } from '@/api/gateway/my-models'
import { GATEWAY_MODELS_STALE_MS, gatewayModelsListQueryKey } from '@/features/gateway-models/utils'
import { MAX_PAGE_SIZE } from '@/lib/pagination'

const scheduleIdleWork: (callback: () => void) => number =
  typeof requestIdleCallback !== 'undefined'
    ? requestIdleCallback
    : (callback) => window.setTimeout(callback, 1)

const cancelIdleWork: (id: number) => void =
  typeof cancelIdleCallback !== 'undefined'
    ? cancelIdleCallback
    : (id) => {
        window.clearTimeout(id)
      }

export type InfiniteModelPrefetchMode = 'none' | 'open' | 'idle'

interface InfinitePagesBaseOptions {
  enabled?: boolean
  prefetchMode?: InfiniteModelPrefetchMode
}

export interface UseInfiniteGatewayModelPagesResult {
  items: GatewayModel[]
  isLoading: boolean
  isSuccess: boolean
  isFetching: boolean
  isFetchingNextPage: boolean
  hasNextPage: boolean
  onPickerOpenChange: (open: boolean) => void
  ensureModelName: (modelName: string) => void
  refetch: () => Promise<unknown>
}

export function useInfiniteGatewayModelPages(
  teamId: string,
  params: Omit<GatewayModelListQuery, 'page' | 'page_size'>,
  options?: InfinitePagesBaseOptions
): UseInfiniteGatewayModelPagesResult {
  const enabled = options?.enabled ?? true
  const prefetchMode = options?.prefetchMode ?? 'none'
  const [pickerOpen, setPickerOpen] = useState(false)
  const [idlePrefetch, setIdlePrefetch] = useState(false)
  const [pendingModelName, setPendingModelName] = useState<string | null>(null)

  const registryScope = params.registry_scope ?? 'team'
  const queryKey = useMemo(
    () =>
      [
        ...gatewayModelsListQueryKey(
          teamId,
          registryScope,
          params.provider ?? '',
          params.credential_id ?? '',
          1,
          MAX_PAGE_SIZE,
          params.q ?? '',
          params.connectivity ?? 'all',
          params.type ?? ''
        ),
        'infinite',
      ] as const,
    [
      teamId,
      registryScope,
      params.provider,
      params.credential_id,
      params.q,
      params.connectivity,
      params.type,
    ]
  )

  const {
    data,
    isLoading,
    isSuccess,
    isFetching,
    isFetchingNextPage,
    hasNextPage,
    fetchNextPage,
    refetch,
  } = useInfiniteQuery({
    queryKey,
    queryFn: ({ pageParam }) =>
      gatewayApi.listModels(teamId, { ...params, page: pageParam, page_size: MAX_PAGE_SIZE }),
    initialPageParam: 1,
    getNextPageParam: (lastPage) => (lastPage.has_next ? lastPage.page + 1 : undefined),
    enabled: enabled && teamId.length > 0,
    staleTime: GATEWAY_MODELS_STALE_MS,
  })

  const items = useMemo(() => data?.pages.flatMap((page) => page.items) ?? [], [data])

  useEffect(() => {
    if (prefetchMode !== 'idle' || !enabled) return
    const id = scheduleIdleWork(() => {
      setIdlePrefetch(true)
    })
    return () => {
      cancelIdleWork(id)
    }
  }, [prefetchMode, enabled])

  const shouldPrefetchMore =
    ((prefetchMode === 'open' && pickerOpen) || (prefetchMode === 'idle' && idlePrefetch)) &&
    hasNextPage &&
    !isFetchingNextPage

  useEffect(() => {
    if (!shouldPrefetchMore) return
    void fetchNextPage()
  }, [shouldPrefetchMore, fetchNextPage, data?.pages.length])

  const modelNames = useMemo(() => new Set(items.map((m) => m.name)), [items])

  const ensureModelName = useCallback((modelName: string): void => {
    const trimmed = modelName.trim()
    if (trimmed) setPendingModelName(trimmed)
  }, [])

  useEffect(() => {
    if (!pendingModelName || modelNames.has(pendingModelName)) {
      if (pendingModelName && modelNames.has(pendingModelName)) {
        setPendingModelName(null)
      }
      return
    }
    if (hasNextPage && !isFetchingNextPage) {
      void fetchNextPage()
      return
    }
    setPendingModelName(null)
  }, [
    pendingModelName,
    modelNames,
    hasNextPage,
    isFetchingNextPage,
    fetchNextPage,
    data?.pages.length,
  ])

  const onPickerOpenChange = useCallback((open: boolean): void => {
    setPickerOpen(open)
  }, [])

  return {
    items,
    isLoading,
    isSuccess,
    isFetching,
    isFetchingNextPage,
    hasNextPage,
    onPickerOpenChange,
    ensureModelName,
    refetch,
  }
}

export interface UseInfinitePersonalModelPagesResult {
  items: PersonalGatewayModel[]
  isLoading: boolean
  isSuccess: boolean
  isFetchingNextPage: boolean
  hasNextPage: boolean
  onPickerOpenChange: (open: boolean) => void
}

export function useInfinitePersonalModelPages(
  params?: Omit<PersonalModelListQuery, 'page' | 'page_size'>,
  options?: InfinitePagesBaseOptions
): UseInfinitePersonalModelPagesResult {
  const enabled = options?.enabled ?? true
  const prefetchMode = options?.prefetchMode ?? 'none'
  const [pickerOpen, setPickerOpen] = useState(false)
  const [idlePrefetch, setIdlePrefetch] = useState(false)

  const queryKey = useMemo(
    () =>
      [
        'gateway',
        'my-models',
        'infinite',
        params?.provider ?? '',
        params?.q ?? '',
        params?.connectivity ?? 'all',
      ] as const,
    [params?.provider, params?.q, params?.connectivity]
  )

  const { data, isLoading, isSuccess, isFetchingNextPage, hasNextPage, fetchNextPage } =
    useInfiniteQuery({
      queryKey,
      queryFn: ({ pageParam }) =>
        gatewayApi.listMyModels({ ...params, page: pageParam, page_size: MAX_PAGE_SIZE }),
      initialPageParam: 1,
      getNextPageParam: (lastPage) => (lastPage.has_next ? lastPage.page + 1 : undefined),
      enabled,
      staleTime: GATEWAY_MODELS_STALE_MS,
    })

  const items = useMemo(() => data?.pages.flatMap((page) => page.items) ?? [], [data])

  useEffect(() => {
    if (prefetchMode !== 'idle' || !enabled) return
    const id = scheduleIdleWork(() => {
      setIdlePrefetch(true)
    })
    return () => {
      cancelIdleWork(id)
    }
  }, [prefetchMode, enabled])

  const shouldPrefetchMore =
    ((prefetchMode === 'open' && pickerOpen) || (prefetchMode === 'idle' && idlePrefetch)) &&
    hasNextPage &&
    !isFetchingNextPage

  useEffect(() => {
    if (!shouldPrefetchMore) return
    void fetchNextPage()
  }, [shouldPrefetchMore, fetchNextPage, data?.pages.length])

  const onPickerOpenChange = useCallback((open: boolean): void => {
    setPickerOpen(open)
  }, [])

  return {
    items,
    isLoading,
    isSuccess,
    isFetchingNextPage,
    hasNextPage,
    onPickerOpenChange,
  }
}
