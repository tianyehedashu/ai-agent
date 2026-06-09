import { useMemo } from 'react'

import { keepPreviousData, useQueries } from '@tanstack/react-query'

import {
  statsApi,
  type GatewayUsageStatsBreakdownQuery,
  type GatewayUsageStatsGroupBy,
  type GatewayUsageStatsItem,
  type UsageStatisticsBreakdownResponse,
} from '@/api/gateway/stats'
import { buildFilterKey } from '@/lib/pagination'

export const TABLE_MODEL_TOP_N = 1
export const TABLE_CREDENTIAL_TOP_N = 32

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
    baseQuery.start ?? '',
    baseQuery.end ?? '',
    baseQuery.usage_aggregation ?? 'workspace',
    baseQuery.credential_id ?? '',
    baseQuery.user_id ?? '',
    baseQuery.filter_team_id ?? '',
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
  breakdownBy: 'credential' | 'model',
  topN: number
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

function usageStatsRowBreakdownQueryKey(
  teamId: string,
  baseQuery: UsageStatsBreakdownBaseQuery,
  parentGroupBy: GatewayUsageStatsGroupBy,
  parentGroupKey: string,
  modelTopN: number,
  credentialTopN: number
): readonly (string | number)[] {
  return [
    'gateway',
    'usage-stats-row-breakdown',
    teamId,
    breakdownBaseQueryKey(teamId, baseQuery),
    parentGroupBy,
    parentGroupKey,
    modelTopN,
    credentialTopN,
  ] as const
}

interface RowBreakdownQueryDef {
  rowKey: string
  queryKey: readonly (string | number)[]
  queryFn: () => Promise<UsageStatsRowBreakdown>
}

async function fetchRowBreakdown(
  teamId: string,
  baseQuery: UsageStatsBreakdownBaseQuery,
  parentGroupBy: GatewayUsageStatsGroupBy,
  rowKey: string,
  credentialTopN: number
): Promise<UsageStatsRowBreakdown> {
  const shared = {
    ...baseQuery,
    parent_group_by: parentGroupBy,
    parent_group_key: rowKey,
  }
  const [model, credential] = await Promise.all([
    statsApi.usageStatsBreakdown(teamId, {
      ...shared,
      breakdown_by: 'model',
      top_n: TABLE_MODEL_TOP_N,
    }),
    statsApi.usageStatsBreakdown(teamId, {
      ...shared,
      breakdown_by: 'credential',
      top_n: credentialTopN,
    }),
  ])
  return { model, credential }
}

export function useUsageStatsBreakdownBatch({
  teamId,
  baseQuery,
  parentGroupBy,
  items,
  enabled,
  credentialTopN = TABLE_CREDENTIAL_TOP_N,
}: {
  teamId: string
  baseQuery: UsageStatsBreakdownBaseQuery
  parentGroupBy: GatewayUsageStatsGroupBy
  items: readonly GatewayUsageStatsItem[]
  enabled: boolean
  credentialTopN?: number
}): {
  breakdownByRowKey: ReadonlyMap<string, UsageStatsRowBreakdown>
  loadingRowKeys: ReadonlySet<string>
  isLoading: boolean
  isFetching: boolean
} {
  const effectiveCredentialTopN = Math.min(Math.max(1, credentialTopN), TABLE_CREDENTIAL_TOP_N)

  const queryDefs = useMemo((): RowBreakdownQueryDef[] => {
    if (!enabled) return []
    const defs: RowBreakdownQueryDef[] = []
    for (const item of items) {
      const rowKey = item.group_key.trim()
      if (!rowKey) continue
      defs.push({
        rowKey,
        queryKey: usageStatsRowBreakdownQueryKey(
          teamId,
          baseQuery,
          parentGroupBy,
          rowKey,
          TABLE_MODEL_TOP_N,
          effectiveCredentialTopN
        ),
        queryFn: () =>
          fetchRowBreakdown(teamId, baseQuery, parentGroupBy, rowKey, effectiveCredentialTopN),
      })
    }
    return defs
  }, [enabled, items, teamId, parentGroupBy, baseQuery, effectiveCredentialTopN])

  const queries = useMemo(
    () =>
      queryDefs.map((def) => ({
        queryKey: def.queryKey,
        queryFn: def.queryFn,
        enabled: enabled && queryDefs.length > 0,
        staleTime: 60_000,
        placeholderData: keepPreviousData,
      })),
    [queryDefs, enabled]
  )

  const results = useQueries({ queries })

  const { breakdownByRowKey, loadingRowKeys } = useMemo(() => {
    const map = new Map<string, UsageStatsRowBreakdown>()
    const loading = new Set<string>()
    queryDefs.forEach((def, index) => {
      const result = results[index]
      if (result.isLoading) {
        loading.add(def.rowKey)
      }
      if (result.data !== undefined) {
        map.set(def.rowKey, result.data)
      }
    })
    return { breakdownByRowKey: map, loadingRowKeys: loading }
  }, [queryDefs, results])

  const isLoading = enabled && results.some((result) => result.isLoading)
  const isFetching = enabled && results.some((result) => result.isFetching)

  return { breakdownByRowKey, loadingRowKeys, isLoading, isFetching }
}
