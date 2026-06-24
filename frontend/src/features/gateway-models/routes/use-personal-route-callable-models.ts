/**
 * 个人虚拟路由可选 callable 模型（跨团队协作团队 + 系统）。
 */

import { useMemo } from 'react'

import { useQuery } from '@tanstack/react-query'

import type { GatewayModel } from '@/api/gateway/models'
import { routesApi, type RouteCallableModel } from '@/api/gateway/routes'

export const MY_ROUTE_CALLABLE_MODELS_QUERY_KEY = ['gateway', 'my-route-callable-models'] as const

/** 编辑面板 combobox 首屏分页大小（全量由批量选择器按需拉取） */
export const PERSONAL_ROUTE_CALLABLE_EDITOR_PAGE_SIZE = 200

export interface RoutePickerModel extends GatewayModel {
  /** 原始注册别名（展示用） */
  registry_name: string
  team_kind: RouteCallableModel['team_kind']
  team_slug: string | null
  prefix_dispatchable: boolean
}

export function routeCallableToPickerModel(item: RouteCallableModel): RoutePickerModel {
  return {
    ...item,
    registry_name: item.name,
    name: item.route_ref,
  }
}

function mapCallableItems(rawItems: readonly RouteCallableModel[]): RoutePickerModel[] {
  return rawItems.map(routeCallableToPickerModel)
}

function extractTeamIds(rawItems: readonly RouteCallableModel[]): string[] {
  return [
    ...new Set(
      rawItems
        .map((item) => item.tenant_id ?? item.team_id)
        .filter((id): id is string => typeof id === 'string' && id.length > 0)
    ),
  ]
}

export interface UsePersonalRouteCallableModelsOptions {
  enabled?: boolean
}

/** 编辑面板用：首屏分页 callable 列表（避免工作区全量翻页） */
export function usePersonalRouteCallableModels(
  options: UsePersonalRouteCallableModelsOptions = {}
): {
  items: readonly RoutePickerModel[]
  rawItems: readonly RouteCallableModel[]
  isLoading: boolean
  isFetching: boolean
  refetch: () => Promise<unknown>
  teamIds: readonly string[]
} {
  const enabled = options.enabled ?? true
  const query = useQuery({
    queryKey: [
      ...MY_ROUTE_CALLABLE_MODELS_QUERY_KEY,
      'editor-page',
      PERSONAL_ROUTE_CALLABLE_EDITOR_PAGE_SIZE,
    ] as const,
    queryFn: async () => {
      const page = await routesApi.listMyRouteCallableModelsPage({
        page: 1,
        page_size: PERSONAL_ROUTE_CALLABLE_EDITOR_PAGE_SIZE,
      })
      return page.items
    },
    enabled,
    staleTime: 30_000,
  })

  const items = useMemo(() => mapCallableItems(query.data ?? []), [query.data])
  const teamIds = useMemo(() => extractTeamIds(query.data ?? []), [query.data])

  return {
    items,
    rawItems: query.data ?? [],
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    refetch: query.refetch,
    teamIds,
  }
}

export interface UsePersonalRouteCallableModelsBatchOptions {
  /** 通常为批量弹窗 open 时为 true */
  enabled?: boolean
}

/** 批量添加弹窗用：按需拉取全量 callable（打开时才请求） */
export function usePersonalRouteCallableModelsBatch(
  options: UsePersonalRouteCallableModelsBatchOptions = {}
): {
  items: readonly RoutePickerModel[]
  isLoading: boolean
  isFetching: boolean
} {
  const enabled = options.enabled ?? false
  const query = useQuery({
    queryKey: [...MY_ROUTE_CALLABLE_MODELS_QUERY_KEY, 'all'] as const,
    queryFn: () => routesApi.listMyRouteCallableModels(),
    enabled,
    staleTime: 30_000,
  })

  const items = useMemo(() => mapCallableItems(query.data ?? []), [query.data])

  return {
    items,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
  }
}
