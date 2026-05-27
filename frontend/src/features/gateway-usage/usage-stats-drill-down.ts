import type { GatewayUsageStatsGroupBy } from '@/api/gateway/stats'

import { GATEWAY_FILTER_ALL } from './gateway-filter-combobox'

export type StatsFilterKey =
  | 'credential_id'
  | 'user_id'
  | 'team_id'
  | 'model'
  | 'provider'
  | 'capability'
  | 'status'
  | 'vkey_id'

export interface UsageStatsDrillSegment {
  label: string
  filterKey: StatsFilterKey
  filterValue: string
  groupByAfter: GatewayUsageStatsGroupBy
}

interface DrillDownMapping {
  filterKey: StatsFilterKey
  groupByAfter: GatewayUsageStatsGroupBy
}

const DRILL_DOWN_MAP: Record<GatewayUsageStatsGroupBy, DrillDownMapping> = {
  user: { filterKey: 'user_id', groupByAfter: 'model' },
  credential: { filterKey: 'credential_id', groupByAfter: 'model' },
  team: { filterKey: 'team_id', groupByAfter: 'credential' },
  model: { filterKey: 'model', groupByAfter: 'credential' },
  vkey: { filterKey: 'vkey_id', groupByAfter: 'model' },
  provider: { filterKey: 'provider', groupByAfter: 'model' },
  capability: { filterKey: 'capability', groupByAfter: 'model' },
  status: { filterKey: 'status', groupByAfter: 'model' },
}

export interface DrillDownNextState {
  segment: UsageStatsDrillSegment
  groupBy: GatewayUsageStatsGroupBy
}

export function drillDownNextState(
  groupBy: GatewayUsageStatsGroupBy,
  groupKey: string,
  label: string
): DrillDownNextState | null {
  const trimmedKey = groupKey.trim()
  if (trimmedKey.length === 0) return null

  const mapping = DRILL_DOWN_MAP[groupBy]
  const displayLabel = label.trim() || trimmedKey

  return {
    segment: {
      label: displayLabel,
      filterKey: mapping.filterKey,
      filterValue: trimmedKey,
      groupByAfter: mapping.groupByAfter,
    },
    groupBy: mapping.groupByAfter,
  }
}

export function filterKeyToStateSetter(key: StatsFilterKey): keyof UsageStatsFilterState {
  switch (key) {
    case 'credential_id':
      return 'credentialId'
    case 'user_id':
      return 'userId'
    case 'team_id':
      return 'teamFilterId'
    case 'model':
      return 'model'
    case 'provider':
      return 'provider'
    case 'capability':
      return 'capability'
    case 'status':
      return 'status'
    case 'vkey_id':
      return 'vkeyId'
  }
}

/** 与 stats 页 useState 字段对齐，供钻取回退使用 */
export interface UsageStatsFilterState {
  credentialId: string
  userId: string
  teamFilterId: string
  model: string
  provider: string
  capability: string
  status: string
  vkeyId: string
}

export function applyDrillSegmentToFilterState(
  state: UsageStatsFilterState,
  segment: UsageStatsDrillSegment
): UsageStatsFilterState {
  const field = filterKeyToStateSetter(segment.filterKey)
  return { ...state, [field]: segment.filterValue }
}

export function clearDrillSegmentsFromFilterState(
  state: UsageStatsFilterState,
  segments: readonly UsageStatsDrillSegment[]
): UsageStatsFilterState {
  let next = { ...state }
  for (const segment of segments) {
    const field = filterKeyToStateSetter(segment.filterKey)
    next = { ...next, [field]: GATEWAY_FILTER_ALL }
  }
  return next
}

export function shouldShowBreakdownColumns(groupBy: GatewayUsageStatsGroupBy): boolean {
  return groupBy !== 'credential' && groupBy !== 'model'
}

export {
  getUsageStatsIdentityColumnHeaders,
  USAGE_STATS_GROUP_OPTIONS,
  usageStatsGroupLabel,
} from './usage-stats-group-options'
