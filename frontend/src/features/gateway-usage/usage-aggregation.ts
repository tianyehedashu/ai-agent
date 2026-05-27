import type { GatewayUsageAggregation } from '@/api/gateway'

export const GATEWAY_USAGE_AGGREGATION_OPTIONS: readonly {
  value: GatewayUsageAggregation
  label: string
  description: string
}[] = [
  {
    value: 'workspace',
    label: '团队',
    description: '按顶部团队切换器选中的当前团队（含个人/共享）统计',
  },
  {
    value: 'user',
    label: '我',
    description: '按当前登录账号跨团队统计',
  },
]

/** 调用统计中「按团队分组 / 团队筛选」仅在跨团队（user）切片下有意义。 */
export function isCrossTeamUsageStatsEnabled(aggregation: GatewayUsageAggregation): boolean {
  return aggregation === 'user'
}
