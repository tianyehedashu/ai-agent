import { useQuery, type UseQueryResult } from '@tanstack/react-query'

import { gatewayApi } from '@/api/gateway'
import type { GatewayBudget } from '@/api/gateway/budgets'

export function gatewayBudgetsQueryKey(
  teamId: string,
  params?: { target_kind?: GatewayBudget['target_kind']; model_name?: string }
): readonly ['gateway', 'budgets', string, string | undefined, string | undefined] {
  return ['gateway', 'budgets', teamId, params?.target_kind, params?.model_name] as const
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
