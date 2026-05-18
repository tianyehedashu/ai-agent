import type { GatewayUsageAggregation } from '@/api/gateway'

export const GATEWAY_USAGE_AGGREGATION_OPTIONS: readonly {
  value: GatewayUsageAggregation
  label: string
  description: string
}[] = [
  {
    value: 'user',
    label: '按账号',
    description: '按当前登录账号跨空间统计',
  },
  {
    value: 'workspace',
    label: '当前空间',
    description: '按顶部团队切换器选中的个人/团队空间统计',
  },
]
