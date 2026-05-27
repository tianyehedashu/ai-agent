import { useMemo } from 'react'

import { useQueries } from '@tanstack/react-query'

import {
  statsApi,
  type GatewayUsageStatsBreakdownQuery,
  type GatewayUsageStatsGroupBy,
  type GatewayUsageStatsItem,
  type UsageStatisticsBreakdownBy,
  type UsageStatisticsBreakdownResponse,
} from '@/api/gateway/stats'
import { buildFilterKey } from '@/lib/pagination'

const TOP_N = 3

export type UsageStatsBreakdownBaseQuery = Omit<
  GatewayUsageStatsBreakdownQuery,
  'parent_group_by' | 'parent_group_key' | 'breakdown_by' | 'top_n'
>

export interface UsageStatsRowBreakdown {
  credential?: UsageStatisticsBreakdownResponse
  model?: UsageStatisticsBreakdownResponse
}

function breakdownBaseQueryKey(teamId: string, baseQuery: UsageStatsBreakdownBaseQuery): string {
  return buildFilterKey([
    teamId,
    baseQuery.days ?? 7,
    baseQuery.usage_aggregation ?? 'workspace',
    baseQuery.credential_id ?? '',
    baseQuery.user_id ?? '',
    baseQuery.team_id ?? '',
    baseQuery.model ?? '',
    baseQuery.provider ?? '',
    baseQuery.capability ?? '',
    baseQuery.status ?? '',
    baseQuery.vkey_id ?? '',
  ])
}

export function usageStatsBreakdownQueryKey(
  teamId: string,
  baseQuery: UsageStatsBreakdownBaseQuery,
  parentGroupBy: GatewayUsageStatsGroupBy,
  parentGroupKey: string,
  breakdownBy: UsageStatisticsBreakdownBy,
  topN: number = TOP_N
): readonly (string | number)[] {
  return [
    'gateway',
    'usage-stats-breakdown',
    teamId,
    breakdownBaseQueryKey(teamId, baseQuery),
    parentGroupBy,
    parentGroupKey,
    breakdownBy,
    topN,
  ] as const
}

interface BreakdownQueryDef {
  rowKey: string
  breakdownBy: UsageStatisticsBreakdownBy
  queryKey: readonly (string | number)[]
  queryFn: () => Promise<UsageStatisticsBreakdownResponse>
}

export function useUsageStatsBreakdownBatch({
  teamId,
  baseQuery,
  parentGroupBy,
  items,
  enabled,
}: {
  teamId: string
  baseQuery: UsageStatsBreakdownBaseQuery
  parentGroupBy: GatewayUsageStatsGroupBy
  items: readonly GatewayUsageStatsItem[]
  enabled: boolean
}): {
  breakdownByRowKey: ReadonlyMap<string, UsageStatsRowBreakdown>
  isLoading: boolean
  isFetching: boolean
} {
  const queryDefs = useMemo((): BreakdownQueryDef[] => {
    if (!enabled) return []
    const defs: BreakdownQueryDef[] = []
    for (const item of items) {
      const rowKey = item.group_key.trim()
      if (!rowKey) continue
      for (const breakdownBy of ['credential', 'model'] as const) {
        defs.push({
          rowKey,
          breakdownBy,
          queryKey: usageStatsBreakdownQueryKey(
            teamId,
            baseQuery,
            parentGroupBy,
            rowKey,
            breakdownBy,
            TOP_N
          ),
          queryFn: () =>
            statsApi.usageStatsBreakdown(teamId, {
              ...baseQuery,
              parent_group_by: parentGroupBy,
              parent_group_key: rowKey,
              breakdown_by: breakdownBy,
              top_n: TOP_N,
            }),
        })
      }
    }
    return defs
  }, [enabled, items, teamId, parentGroupBy, baseQuery])

  const results = useQueries({
    queries: queryDefs.map((def) => ({
      queryKey: def.queryKey,
      queryFn: def.queryFn,
      enabled: enabled && queryDefs.length > 0,
      staleTime: 60_000,
    })),
  })

  const breakdownByRowKey = useMemo((): ReadonlyMap<string, UsageStatsRowBreakdown> => {
    const map = new Map<string, UsageStatsRowBreakdown>()
    queryDefs.forEach((def, index) => {
      const data = results[index]?.data
      if (!data) return
      const existing = map.get(def.rowKey) ?? {}
      if (def.breakdownBy === 'credential') {
        map.set(def.rowKey, { ...existing, credential: data })
      } else {
        map.set(def.rowKey, { ...existing, model: data })
      }
    })
    return map
  }, [queryDefs, results])

  const isLoading = enabled && results.some((result) => result.isLoading)
  const isFetching = enabled && results.some((result) => result.isFetching)

  return { breakdownByRowKey, isLoading, isFetching }
}

export { TOP_N as USAGE_STATS_BREAKDOWN_TOP_N }
