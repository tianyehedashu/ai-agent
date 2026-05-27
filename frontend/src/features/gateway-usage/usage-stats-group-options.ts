import type { GatewayUsageStatsGroupBy } from '@/api/gateway/stats'

export const USAGE_STATS_GROUP_OPTIONS: ReadonlyArray<{
  value: GatewayUsageStatsGroupBy
  label: string
}> = [
  { value: 'credential', label: '凭据' },
  { value: 'user', label: '人员' },
  { value: 'team', label: '团队' },
  { value: 'model', label: '模型' },
  { value: 'vkey', label: '虚拟 Key' },
  { value: 'provider', label: '提供商' },
  { value: 'capability', label: '能力' },
  { value: 'status', label: '状态' },
]

const GROUP_LABEL_BY_VALUE = Object.fromEntries(
  USAGE_STATS_GROUP_OPTIONS.map((option) => [option.value, option.label])
) as Record<GatewayUsageStatsGroupBy, string>

const IDENTITY_COLUMN_HEADERS_CACHE = new Map<
  GatewayUsageStatsGroupBy,
  readonly [string, string, string]
>()

export function usageStatsGroupLabel(groupBy: GatewayUsageStatsGroupBy): string {
  return GROUP_LABEL_BY_VALUE[groupBy]
}

/** 身份区三列表头：父维度 | 模型 | 凭据（各占一列）。 */
export function getUsageStatsIdentityColumnHeaders(
  groupBy: GatewayUsageStatsGroupBy
): readonly [parentLabel: string, modelLabel: string, credentialLabel: string] {
  const cached = IDENTITY_COLUMN_HEADERS_CACHE.get(groupBy)
  if (cached) return cached
  const headers: readonly [string, string, string] = [usageStatsGroupLabel(groupBy), '模型', '凭据']
  IDENTITY_COLUMN_HEADERS_CACHE.set(groupBy, headers)
  return headers
}
