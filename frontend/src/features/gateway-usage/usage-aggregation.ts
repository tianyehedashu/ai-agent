import type { GatewayUsageAggregation } from '@/api/gateway'

export interface GatewayUsageAggregationOption {
  value: GatewayUsageAggregation
  label: string
  description: string
}

export const GATEWAY_USAGE_AGGREGATION_OPTIONS: readonly GatewayUsageAggregationOption[] = [
  {
    value: 'workspace',
    label: '团队',
    description: '按 URL 当前团队（/gateway/teams/:teamId，含个人/共享）统计',
  },
  {
    value: 'user',
    label: '我',
    description: '按当前登录账号跨团队统计',
  },
]

/** 全平台切片：覆盖所有用户，仅平台管理员可见。 */
export const PLATFORM_USAGE_AGGREGATION_OPTION: GatewayUsageAggregationOption = {
  value: 'platform',
  label: '全平台',
  description: '覆盖全平台所有用户的调用（仅平台管理员可见）',
}

/** 按当前用户权限返回可用聚合切片：平台管理员额外可选「全平台」。 */
export function gatewayUsageAggregationOptions(
  isPlatformAdmin: boolean
): readonly GatewayUsageAggregationOption[] {
  return isPlatformAdmin
    ? [...GATEWAY_USAGE_AGGREGATION_OPTIONS, PLATFORM_USAGE_AGGREGATION_OPTION]
    : GATEWAY_USAGE_AGGREGATION_OPTIONS
}

/** 调用统计中「按团队分组 / 团队筛选」在跨团队（user / platform）切片下有意义。 */
export function isCrossTeamUsageStatsEnabled(aggregation: GatewayUsageAggregation): boolean {
  return aggregation === 'user' || aggregation === 'platform'
}

/** 日志/概览页副标题：当前用量切片范围说明。 */
export function usageAggregationScopeLabel(aggregation: GatewayUsageAggregation): string {
  if (aggregation === 'platform') return '全平台调用'
  if (aggregation === 'user') return '我的跨团队调用'
  return '当前团队调用'
}
