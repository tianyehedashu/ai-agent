/**
 * 虚拟 Key 列表页：并行预取各 Key 的 entitlement（避免每行独立 mount 造成请求瀑布）。
 */

import { useMemo } from 'react'

import { useQueries } from '@tanstack/react-query'

import { gatewayApi, type EntitlementPlan } from '@/api/gateway'

const ENTITLEMENTS_STALE_MS = 5 * 60_000

export function filterActiveEntitlementPlans(plans: readonly EntitlementPlan[]): EntitlementPlan[] {
  const now = Date.now()
  return plans.filter(
    (plan) =>
      plan.is_active &&
      new Date(plan.valid_from).getTime() <= now &&
      new Date(plan.valid_until).getTime() > now
  )
}

export function useKeysEntitlementsMap(vkeyIds: readonly string[]): {
  activeByVkeyId: Map<string, EntitlementPlan[]>
  isLoadingByVkeyId: Map<string, boolean>
} {
  const queries = useQueries({
    queries: vkeyIds.map((id) => ({
      queryKey: ['gateway', 'keys', id, 'entitlements'] as const,
      queryFn: () => gatewayApi.listVkeyEntitlements(id),
      enabled: id.length > 0,
      staleTime: ENTITLEMENTS_STALE_MS,
    })),
  })

  const querySnapshot = queries
    .map((row, index) => `${vkeyIds[index]}:${String(row.isLoading)}:${String(row.dataUpdatedAt)}`)
    .join('|')

  return useMemo(() => {
    const activeByVkeyId = new Map<string, EntitlementPlan[]>()
    const isLoadingByVkeyId = new Map<string, boolean>()
    for (let index = 0; index < vkeyIds.length; index += 1) {
      const id = vkeyIds[index]
      const row = queries[index]
      isLoadingByVkeyId.set(id, row.isLoading)
      activeByVkeyId.set(id, filterActiveEntitlementPlans(row.data ?? []))
    }
    return { activeByVkeyId, isLoadingByVkeyId }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- querySnapshot 反映 queries 代际
  }, [vkeyIds, querySnapshot])
}
