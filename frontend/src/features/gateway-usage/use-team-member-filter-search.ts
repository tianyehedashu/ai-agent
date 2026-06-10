/**
 * 团队成员筛选下拉：服务端搜索 Hook。
 *
 * 下拉打开时按搜索词请求后端分页接口，避免全量加载（人员超多场景）。
 * 复用 GatewayFilterCombobox 的 searchMode='server' 能力。
 */

import { useDeferredValue, useMemo, useState } from 'react'

import { useQuery } from '@tanstack/react-query'

import { teamsApi } from '@/api/gateway/teams'
import {
  GATEWAY_FILTER_ALL,
  type GatewayFilterOption,
} from '@/features/gateway-usage/gateway-filter-combobox'
import { memberFilterOptionsFromTeamMembers } from '@/features/gateway-usage/usage-stats-filter-catalog'

/** 单次请求条数 */
const TEAM_MEMBER_FILTER_PAGE_SIZE = 40

export interface UseTeamMemberFilterSearchParams {
  teamId: string
  selectedUserId: string
  enabled: boolean
}

export interface TeamMemberFilterSearchResult {
  options: GatewayFilterOption[]
  onSearchQueryChange: (query: string) => void
  onPickerOpenChange: (open: boolean) => void
  remoteSearching: boolean
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

export function useTeamMemberFilterSearch({
  teamId,
  selectedUserId,
  enabled,
}: UseTeamMemberFilterSearchParams): TeamMemberFilterSearchResult {
  const [search, setSearch] = useState('')
  const [pickerOpen, setPickerOpen] = useState(false)
  const deferredSearch = useDeferredValue(search.trim())

  const listQuery = useQuery({
    queryKey: ['gateway', 'member-filter', teamId, deferredSearch],
    queryFn: () =>
      teamsApi.listMembersPage(teamId, {
        search: deferredSearch.length > 0 ? deferredSearch : undefined,
        page: 1,
        page_size: TEAM_MEMBER_FILTER_PAGE_SIZE,
      }),
    enabled: enabled && pickerOpen,
    staleTime: 30_000,
  })

  // 已选用户标签解析：用全量接口查找（仅触发一次，长 staleTime）
  const selectedQuery = useQuery({
    queryKey: ['gateway', 'members', teamId],
    queryFn: () => teamsApi.listMembers(teamId),
    enabled: enabled && selectedUserId !== GATEWAY_FILTER_ALL,
    staleTime: 300_000,
    select: (members) => members.find((m) => m.user_id === selectedUserId) ?? null,
  })

  const options = useMemo(() => {
    const fromList = memberFilterOptionsFromTeamMembers(listQuery.data?.items ?? [])
    const selectedOption = selectedQuery.isSuccess
      ? (memberFilterOptionsFromTeamMembers(selectedQuery.data ? [selectedQuery.data] : [])[0] ??
        null)
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
