import { useDeferredValue, useMemo, useState } from 'react'

import { useQuery } from '@tanstack/react-query'

import { adminUsersApi } from '@/api/admin-users'
import {
  GATEWAY_FILTER_ALL,
  type GatewayFilterOption,
} from '@/features/gateway-usage/gateway-filter-combobox'
import { memberFilterOptionsFromPlatformUsers } from '@/features/gateway-usage/usage-stats-filter-catalog'

/** 统计页人员下拉单次请求条数（避免全量拉取） */
export const PLATFORM_USER_STATS_FILTER_PAGE_SIZE = 40

export interface UsePlatformUserStatsFilterSearchParams {
  selectedUserId: string
  enabled: boolean
}

export interface PlatformUserStatsFilterSearchResult {
  options: GatewayFilterOption[]
  onSearchQueryChange: (query: string) => void
  onPickerOpenChange: (open: boolean) => void
  remoteSearching: boolean
  /** 已选用户标签解析中（用于触发器） */
  resolvingSelection: boolean
}

function mergeSelectedIntoOptions(
  options: GatewayFilterOption[],
  selected: GatewayFilterOption | null
): GatewayFilterOption[] {
  if (selected === null) return options
  if (options.some((option) => option.value === selected.value)) return options
  return [selected, ...options]
}

export function usePlatformUserStatsFilterSearch({
  selectedUserId,
  enabled,
}: UsePlatformUserStatsFilterSearchParams): PlatformUserStatsFilterSearchResult {
  const [search, setSearch] = useState('')
  const [pickerOpen, setPickerOpen] = useState(false)
  const deferredSearch = useDeferredValue(search.trim())

  const listQuery = useQuery({
    queryKey: ['gateway', 'stats-filter', 'platform-users', deferredSearch],
    queryFn: () =>
      adminUsersApi.list({
        search: deferredSearch.length > 0 ? deferredSearch : undefined,
        is_active: true,
        page: 1,
        page_size: PLATFORM_USER_STATS_FILTER_PAGE_SIZE,
      }),
    enabled: enabled && pickerOpen,
    staleTime: 30_000,
  })

  const selectedQuery = useQuery({
    queryKey: ['gateway', 'stats-filter', 'platform-user', selectedUserId],
    queryFn: () => adminUsersApi.getById(selectedUserId),
    enabled: enabled && selectedUserId !== GATEWAY_FILTER_ALL,
    staleTime: 300_000,
  })

  const options = useMemo(() => {
    const fromList = memberFilterOptionsFromPlatformUsers(listQuery.data?.items ?? [])
    const selectedOption = selectedQuery.isSuccess
      ? memberFilterOptionsFromPlatformUsers([selectedQuery.data])[0]
      : null
    return mergeSelectedIntoOptions(fromList, selectedOption ?? null)
  }, [listQuery.data?.items, selectedQuery.data, selectedQuery.isSuccess])

  const resolvingSelection = selectedUserId !== GATEWAY_FILTER_ALL && selectedQuery.isLoading

  return {
    options,
    onSearchQueryChange: setSearch,
    onPickerOpenChange: (open) => {
      setPickerOpen(open)
      if (!open) setSearch('')
    },
    remoteSearching: listQuery.isFetching,
    resolvingSelection,
  }
}
