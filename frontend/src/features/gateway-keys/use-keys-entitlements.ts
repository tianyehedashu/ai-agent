/**
 * 虚拟 Key 列表页：批量拉取客户套餐（GET /managed-team-vkey-entitlements）。
 */

import { useMemo } from 'react'

import { useQuery } from '@tanstack/react-query'

import { gatewayApi, type EntitlementPlan } from '@/api/gateway'

const ENTITLEMENTS_STALE_MS = 5 * 60_000

export const MANAGED_TEAM_VKEY_ENTITLEMENTS_QUERY_KEY = [
  'gateway',
  'managed-team-vkey-entitlements',
] as const

export function filterActiveEntitlementPlans(plans: readonly EntitlementPlan[]): EntitlementPlan[] {
  // plan 头已退化为容器：活性/有效期由 quota 行承载，列表层仅按 valid_from 是否生效过滤。
  const now = Date.now()
  return plans.filter((plan) => new Date(plan.valid_from).getTime() <= now)
}

export function useKeysEntitlementsMap(vkeyIds: readonly string[]): {
  activeByVkeyId: Map<string, EntitlementPlan[]>
  isLoadingByVkeyId: Map<string, boolean>
} {
  const enabled = vkeyIds.length > 0
  const { data, isLoading } = useQuery({
    queryKey: MANAGED_TEAM_VKEY_ENTITLEMENTS_QUERY_KEY,
    queryFn: () => gatewayApi.listManagedTeamVkeyEntitlements(),
    enabled,
    staleTime: ENTITLEMENTS_STALE_MS,
  })

  return useMemo(() => {
    const activeByVkeyId = new Map<string, EntitlementPlan[]>()
    const isLoadingByVkeyId = new Map<string, boolean>()
    const plansByVkeyId = new Map(
      (data?.items ?? []).map((item) => [item.vkey_id, item.plans] as const)
    )
    for (const id of vkeyIds) {
      isLoadingByVkeyId.set(id, isLoading)
      activeByVkeyId.set(id, filterActiveEntitlementPlans(plansByVkeyId.get(id) ?? []))
    }
    return { activeByVkeyId, isLoadingByVkeyId }
  }, [data, isLoading, vkeyIds])
}
