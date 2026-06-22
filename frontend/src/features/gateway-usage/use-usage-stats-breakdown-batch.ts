import { useMemo } from 'react'

import { keepPreviousData, useQuery } from '@tanstack/react-query'

import {
  statsApi,
  type GatewayUsageStatsBreakdownQuery,
  type GatewayUsageStatsGroupBy,
  type GatewayUsageStatsItem,
  type UsageStatisticsBreakdownBatchResponse,
  type UsageStatisticsBreakdownResponse,
} from '@/api/gateway/stats'
import { GATEWAY_USAGE_STATS_STALE_MS } from '@/features/gateway-usage/usage-stats-query'
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

/** 批量响应 → 父行键索引，复用单行 breakdown 的展示结构。 */
function indexBatchByParent(
  data: UsageStatisticsBreakdownBatchResponse | undefined,
  parentGroupBy: GatewayUsageStatsGroupBy,
  breakdownBy: 'model' | 'credential'
): Map<string, UsageStatisticsBreakdownResponse> {
  const map = new Map<string, UsageStatisticsBreakdownResponse>()
  if (!data) return map
  for (const parent of data.items) {
    map.set(parent.parent_group_key, {
      parent_group_by: parentGroupBy,
      parent_group_key: parent.parent_group_key,
      breakdown_by: breakdownBy,
      parent_requests: parent.parent_requests,
      items: parent.items,
    })
  }
  return map
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

  const rowKeys = useMemo(
    () => items.map((item) => item.group_key.trim()).filter((key) => key.length > 0),
    [items]
  )
  const rowKeysKey = useMemo(() => buildFilterKey(rowKeys), [rowKeys])
  const batchEnabled = enabled && rowKeys.length > 0
  const baseKey = breakdownBaseQueryKey(teamId, baseQuery)

  const modelQuery = useQuery({
    queryKey: [
      'gateway',
      'usage-stats-breakdown-batch',
      teamId,
      baseKey,
      parentGroupBy,
      'model',
      TABLE_MODEL_TOP_N,
      rowKeysKey,
    ],
    queryFn: () =>
      statsApi.usageStatsBreakdownBatch(teamId, {
        ...baseQuery,
        parent_group_by: parentGroupBy,
        parent_group_keys: rowKeys,
        breakdown_by: 'model',
        top_n: TABLE_MODEL_TOP_N,
      }),
    enabled: batchEnabled,
    staleTime: GATEWAY_USAGE_STATS_STALE_MS,
    placeholderData: keepPreviousData,
  })

  const credentialQuery = useQuery({
    queryKey: [
      'gateway',
      'usage-stats-breakdown-batch',
      teamId,
      baseKey,
      parentGroupBy,
      'credential',
      effectiveCredentialTopN,
      rowKeysKey,
    ],
    queryFn: () =>
      statsApi.usageStatsBreakdownBatch(teamId, {
        ...baseQuery,
        parent_group_by: parentGroupBy,
        parent_group_keys: rowKeys,
        breakdown_by: 'credential',
        top_n: effectiveCredentialTopN,
      }),
    enabled: batchEnabled,
    staleTime: GATEWAY_USAGE_STATS_STALE_MS,
    placeholderData: keepPreviousData,
  })

  const { breakdownByRowKey, loadingRowKeys } = useMemo(() => {
    const modelByKey = indexBatchByParent(modelQuery.data, parentGroupBy, 'model')
    const credentialByKey = indexBatchByParent(credentialQuery.data, parentGroupBy, 'credential')
    const map = new Map<string, UsageStatsRowBreakdown>()
    for (const rowKey of rowKeys) {
      map.set(rowKey, {
        model: modelByKey.get(rowKey),
        credential: credentialByKey.get(rowKey),
      })
    }
    const loading = new Set<string>()
    if (batchEnabled && (modelQuery.isLoading || credentialQuery.isLoading)) {
      for (const rowKey of rowKeys) loading.add(rowKey)
    }
    return { breakdownByRowKey: map, loadingRowKeys: loading }
  }, [
    modelQuery.data,
    modelQuery.isLoading,
    credentialQuery.data,
    credentialQuery.isLoading,
    rowKeys,
    parentGroupBy,
    batchEnabled,
  ])

  const isLoading = batchEnabled && (modelQuery.isLoading || credentialQuery.isLoading)
  const isFetching = batchEnabled && (modelQuery.isFetching || credentialQuery.isFetching)

  return { breakdownByRowKey, loadingRowKeys, isLoading, isFetching }
}
