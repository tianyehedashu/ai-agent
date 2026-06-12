import type { GatewayModelRouteUsageItem } from '@/api/gateway/models'

/** 将 usage-summary items 索引为 route_name → row（列表 / 详情共用）。 */
export function indexUsageByRouteName(
  items: readonly GatewayModelRouteUsageItem[] | undefined
): Map<string, GatewayModelRouteUsageItem> {
  const map = new Map<string, GatewayModelRouteUsageItem>()
  for (const row of items ?? []) {
    map.set(row.route_name, row)
  }
  return map
}
