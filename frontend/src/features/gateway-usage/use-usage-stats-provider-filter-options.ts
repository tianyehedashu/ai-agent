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
import { GATEWAY_USAGE_STATS_STALE_MS } from '@/features/gateway-usage/usage-stats-query'
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
  /** 为 true 时拉取 statistics(provider) 与 profiles；否则仅用凭据/模型注册表。 */
  discoverFromUsage: boolean
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
  discoverFromUsage,
}: UseUsageStatsProviderFilterOptionsParams): UsageStatsProviderFilterOptionsResult {
  const discoveryEnabled = enabled && discoverFromUsage && teamId.length > 0

  const profilesQuery = useQuery({
    queryKey: ['gateway', 'provider-profiles'],
    queryFn: () => providerProfilesApi.listProviderProfiles(),
    enabled: discoveryEnabled,
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
    enabled: discoveryEnabled,
    staleTime: GATEWAY_USAGE_STATS_STALE_MS,
  })

  const options = useMemo(
    () =>
      mergeProviderFilterOptions(
        discoverFromUsage
          ? providerFilterOptionsFromUsageItems(usageProvidersQuery.data?.items ?? [])
          : [],
        registryProviders,
        discoverFromUsage
          ? providerFilterOptionsFromProfiles(profilesQuery.data?.profiles ?? [])
          : []
      ),
    [
      discoverFromUsage,
      usageProvidersQuery.data?.items,
      registryProviders,
      profilesQuery.data?.profiles,
    ]
  )

  const loading =
    discoveryEnabled &&
    (usageProvidersQuery.isLoading || (profilesQuery.isLoading && options.length === 0))

  return { options, loading }
}
