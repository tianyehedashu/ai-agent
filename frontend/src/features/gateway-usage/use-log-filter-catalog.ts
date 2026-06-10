/**
 * 调用日志页筛选下拉的数据源 Hook。
 *
 * 复用统计页 catalog 逻辑，但仅聚焦当前团队数据（日志页不涉及跨团队/全平台 catalog）。
 * 人员筛选已改用 useTeamMemberFilterSearch（服务端搜索），本 hook 不再提供 memberOptions。
 */

import { useMemo } from 'react'

import { useQuery } from '@tanstack/react-query'

import { credentialsApi } from '@/api/gateway/credentials'
import { keysApi } from '@/api/gateway/keys'
import { useInfiniteGatewayModelPages } from '@/features/gateway-models/hooks/use-infinite-gateway-model-pages'
import type { GatewayFilterOption } from '@/features/gateway-usage/gateway-filter-combobox'
import {
  credentialFilterOptions,
  keyFilterOptions,
  modelFilterOptionsForStats,
} from '@/features/gateway-usage/usage-stats-filter-catalog'

export interface UseLogFilterCatalogParams {
  teamId: string
}

export interface LogFilterCatalogResult {
  credentialOptions: GatewayFilterOption[]
  keyOptions: GatewayFilterOption[]
  modelOptions: GatewayFilterOption[]
  credentialsLoading: boolean
  keysLoading: boolean
  modelsLoading: boolean
}

export function useLogFilterCatalog({ teamId }: UseLogFilterCatalogParams): LogFilterCatalogResult {
  const teamCredentialsQuery = useQuery({
    queryKey: ['gateway', 'credential-summaries', teamId],
    queryFn: () => credentialsApi.listCredentialSummaries(teamId),
  })

  const teamKeysQuery = useQuery({
    queryKey: ['gateway', 'keys', teamId],
    queryFn: () => keysApi.listKeys(teamId),
  })

  const teamModels = useInfiniteGatewayModelPages(
    teamId,
    { registry_scope: 'callable' },
    { prefetchMode: 'open' }
  )

  const credentialOptions = useMemo(
    () => credentialFilterOptions(teamCredentialsQuery.data ?? []),
    [teamCredentialsQuery.data]
  )

  const keyOptions = useMemo(() => keyFilterOptions(teamKeysQuery.data ?? []), [teamKeysQuery.data])

  const modelOptions = useMemo(
    () => modelFilterOptionsForStats(teamModels.items),
    [teamModels.items]
  )

  return {
    credentialOptions,
    keyOptions,
    modelOptions,
    credentialsLoading: teamCredentialsQuery.isLoading,
    keysLoading: teamKeysQuery.isLoading,
    modelsLoading: teamModels.isLoading,
  }
}
