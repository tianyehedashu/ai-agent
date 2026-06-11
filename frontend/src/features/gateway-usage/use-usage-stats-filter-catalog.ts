import { useMemo } from 'react'

import { useQuery } from '@tanstack/react-query'

import { credentialsApi, fetchAllManagedTeamCredentials } from '@/api/gateway/credentials'
import { keysApi } from '@/api/gateway/keys'
import type { GatewayUsageAggregation } from '@/api/gateway/logs'
import { fetchAllManagedTeamModelPages } from '@/api/gateway/models'
import { teamsApi } from '@/api/gateway/teams'
import { useGatewayVirtualKeys } from '@/features/gateway-keys/use-gateway-virtual-keys'
import { useInfiniteGatewayModelPages } from '@/features/gateway-models/hooks/use-infinite-gateway-model-pages'
import { gatewayTeamMembersQueryKey } from '@/features/gateway-teams/use-gateway-team-members'
import type { GatewayFilterOption } from '@/features/gateway-usage/gateway-filter-combobox'
import {
  credentialFilterOptions,
  keyFilterOptions,
  memberFilterOptionsFromTeamMembers,
  modelFilterOptionsForStats,
  registryProviderFilterOptions,
  usageStatsShowMemberFilter,
} from '@/features/gateway-usage/usage-stats-filter-catalog'

export interface UseUsageStatsFilterCatalogParams {
  teamId: string
  usageAggregation: GatewayUsageAggregation
  isPlatformAdmin: boolean
  crossTeamStatsEnabled: boolean
}

export interface UsageStatsFilterCatalogResult {
  showMemberFilter: boolean
  /** 全平台切片：人员筛选项改由服务端搜索（见 usePlatformUserStatsFilterSearch） */
  usePlatformUserDirectory: boolean
  credentialOptions: GatewayFilterOption[]
  memberOptions: GatewayFilterOption[]
  modelOptions: GatewayFilterOption[]
  registryProviderOptions: GatewayFilterOption[]
  keyOptions: GatewayFilterOption[]
  credentialsLoading: boolean
  membersLoading: boolean
  modelsLoading: boolean
  keysLoading: boolean
}

export function useUsageStatsFilterCatalog({
  teamId,
  usageAggregation,
  isPlatformAdmin,
  crossTeamStatsEnabled,
}: UseUsageStatsFilterCatalogParams): UsageStatsFilterCatalogResult {
  const useCrossTeamCatalog = crossTeamStatsEnabled
  const showMemberFilter = usageStatsShowMemberFilter(usageAggregation)
  const usePlatformUserDirectory =
    useCrossTeamCatalog && usageAggregation === 'platform' && isPlatformAdmin

  const teamCredentialsQuery = useQuery({
    queryKey: ['gateway', 'credential-summaries', teamId],
    queryFn: () => credentialsApi.listCredentialSummaries(teamId),
    enabled: !useCrossTeamCatalog,
  })

  const managedCredentialsQuery = useQuery({
    queryKey: ['gateway', 'stats-filter-catalog', 'managed-credentials'],
    queryFn: () => fetchAllManagedTeamCredentials(),
    enabled: useCrossTeamCatalog,
    staleTime: 60_000,
  })

  const teamMembersQuery = useQuery({
    queryKey: gatewayTeamMembersQueryKey(teamId),
    queryFn: () => teamsApi.listMembers(teamId),
    enabled: showMemberFilter && !usePlatformUserDirectory && !useCrossTeamCatalog,
  })

  const teamKeysQuery = useGatewayVirtualKeys(teamId, {
    enabled: !useCrossTeamCatalog,
  })

  const managedKeysQuery = useQuery({
    queryKey: ['gateway', 'stats-filter-catalog', 'managed-keys'],
    queryFn: () => keysApi.listManagedTeamKeys(),
    enabled: useCrossTeamCatalog,
    staleTime: 60_000,
  })

  const teamModels = useInfiniteGatewayModelPages(
    teamId,
    { registry_scope: 'callable' },
    { enabled: !useCrossTeamCatalog, prefetchMode: 'open' }
  )

  const managedModelsQuery = useQuery({
    queryKey: ['gateway', 'stats-filter-catalog', 'managed-models'],
    queryFn: () => fetchAllManagedTeamModelPages(),
    enabled: useCrossTeamCatalog,
    staleTime: 60_000,
  })

  const credentials = useCrossTeamCatalog
    ? (managedCredentialsQuery.data ?? [])
    : (teamCredentialsQuery.data ?? [])

  const models: readonly { name: string; real_model: string; provider: string }[] =
    useCrossTeamCatalog ? (managedModelsQuery.data ?? []) : teamModels.items

  const credentialOptions = useMemo(() => credentialFilterOptions(credentials), [credentials])

  const memberOptions = useMemo(() => {
    if (!showMemberFilter || usePlatformUserDirectory) return []
    return memberFilterOptionsFromTeamMembers(teamMembersQuery.data ?? [])
  }, [showMemberFilter, usePlatformUserDirectory, teamMembersQuery.data])

  const modelOptions = useMemo(() => modelFilterOptionsForStats(models), [models])

  const registryProviderOptions = useMemo(
    () => registryProviderFilterOptions(credentials, models),
    [credentials, models]
  )

  const keyOptions = useMemo(() => {
    const keys = useCrossTeamCatalog ? (managedKeysQuery.data ?? []) : (teamKeysQuery.data ?? [])
    return keyFilterOptions(keys)
  }, [useCrossTeamCatalog, managedKeysQuery.data, teamKeysQuery.data])

  return {
    showMemberFilter,
    usePlatformUserDirectory,
    credentialOptions,
    memberOptions,
    modelOptions,
    registryProviderOptions,
    keyOptions,
    credentialsLoading: useCrossTeamCatalog
      ? managedCredentialsQuery.isLoading
      : teamCredentialsQuery.isLoading,
    membersLoading: usePlatformUserDirectory ? false : teamMembersQuery.isLoading,
    modelsLoading: useCrossTeamCatalog ? managedModelsQuery.isLoading : teamModels.isLoading,
    keysLoading: useCrossTeamCatalog ? managedKeysQuery.isLoading : teamKeysQuery.isLoading,
  }
}
