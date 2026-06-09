import { useMemo } from 'react'

import { useQuery } from '@tanstack/react-query'

import type { GatewayUsageAggregation } from '@/api/gateway/logs'
import { providerProfilesApi } from '@/api/gateway/provider-profiles'
import { statsApi, type GatewayUsageStatsQuery } from '@/api/gateway/stats'
import type { GatewayFilterOption } from '@/features/gateway-usage/gateway-filter-combobox'
import type { UsageStatsDateRangeQuery } from '@/features/gateway-usage/usage-stats-date-range'
import {
  mergeProviderFilterOptions,
  providerFilterOptionsFromProfiles,
  providerFilterOptionsFromUsageItems,
} from '@/features/gateway-usage/usage-stats-filter-catalog'
import { MAX_PAGE_SIZE } from '@/lib/pagination'

export type UsageStatsProviderDiscoveryFilters = Omit<
  GatewayUsageStatsQuery,
  'group_by' | 'page' | 'page_size' | 'provider' | 'days' | 'start' | 'end' | 'usage_aggregation'
>

export interface UseUsageStatsProviderFilterOptionsParams {
  teamId: string
  dateRangeQuery: UsageStatsDateRangeQuery
  usageAggregation: GatewayUsageAggregation
  baseFilters: UsageStatsProviderDiscoveryFilters
  registryProviders: readonly GatewayFilterOption[]
  enabled: boolean
}

export interface UsageStatsProviderFilterOptionsResult {
  options: GatewayFilterOption[]
  loading: boolean
}

export function useUsageStatsProviderFilterOptions({
  teamId,
  dateRangeQuery,
  usageAggregation,
  baseFilters,
  registryProviders,
  enabled,
}: UseUsageStatsProviderFilterOptionsParams): UsageStatsProviderFilterOptionsResult {
  const profilesQuery = useQuery({
    queryKey: ['gateway', 'provider-profiles'],
    queryFn: () => providerProfilesApi.listProviderProfiles(),
    enabled,
    staleTime: 300_000,
  })

  const usageProvidersQuery = useQuery({
    queryKey: [
      'gateway',
      'stats-filter',
      'providers-by-usage',
      teamId,
      dateRangeQuery,
      usageAggregation,
      baseFilters,
    ],
    queryFn: () =>
      statsApi.usageStats(teamId, {
        ...dateRangeQuery,
        usage_aggregation: usageAggregation,
        group_by: 'provider',
        page: 1,
        page_size: MAX_PAGE_SIZE,
        ...baseFilters,
      }),
    enabled: enabled && teamId.length > 0,
    staleTime: 60_000,
  })

  const options = useMemo(
    () =>
      mergeProviderFilterOptions(
        providerFilterOptionsFromUsageItems(usageProvidersQuery.data?.items ?? []),
        registryProviders,
        providerFilterOptionsFromProfiles(profilesQuery.data?.profiles ?? [])
      ),
    [usageProvidersQuery.data?.items, registryProviders, profilesQuery.data?.profiles]
  )

  const loading = usageProvidersQuery.isLoading || (profilesQuery.isLoading && options.length === 0)

  return { options, loading }
}
