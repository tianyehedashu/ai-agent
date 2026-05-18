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
