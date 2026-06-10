import { useQuery, type UseQueryResult } from '@tanstack/react-query'

import { gatewayApi } from '@/api/gateway'
import type { GatewayBudget } from '@/api/gateway/budgets'

/** 团队预算缓存基键：mutation 后用它做前缀失效，可命中任意参数组合的列表缓存。 */
export function gatewayBudgetsBaseQueryKey(
  teamId: string
): readonly ['gateway', 'budgets', string] {
  return ['gateway', 'budgets', teamId] as const
}

export function gatewayBudgetsQueryKey(
  teamId: string,
  params?: { target_kind?: GatewayBudget['target_kind']; model_name?: string }
): readonly unknown[] {
  if (!params) return gatewayBudgetsBaseQueryKey(teamId)
  return [...gatewayBudgetsBaseQueryKey(teamId), params.target_kind, params.model_name] as const
}

export function useGatewayBudgets(
  teamId: string,
  params?: { target_kind?: GatewayBudget['target_kind']; model_name?: string }
): UseQueryResult<GatewayBudget[]> {
  return useQuery({
    queryKey: gatewayBudgetsQueryKey(teamId, params),
    queryFn: () => gatewayApi.listBudgets(teamId, params),
    enabled: teamId.length > 0,
  })
}
