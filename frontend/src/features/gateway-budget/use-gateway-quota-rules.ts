import { useQuery, type UseQueryResult } from '@tanstack/react-query'

import { gatewayApi } from '@/api/gateway'
import type { ListQuotaRulesParams, QuotaRule } from '@/api/gateway/quota-rules'

/** 配额规则与标签元数据缓存 60s，避免切换筛选时重复请求。 */
export const GATEWAY_QUOTA_META_STALE_MS = 60_000

/** 配额规则缓存基键：mutation 后用它做前缀失效，可命中任意参数组合的列表缓存。 */
export function gatewayQuotaRulesBaseQueryKey(
  teamId: string
): readonly ['gateway-quota-rules', string] {
  return ['gateway-quota-rules', teamId] as const
}

export function gatewayQuotaRulesQueryKey(
  teamId: string,
  params?: ListQuotaRulesParams
): readonly unknown[] {
  if (!params) return gatewayQuotaRulesBaseQueryKey(teamId)
  return [...gatewayQuotaRulesBaseQueryKey(teamId), params] as const
}

export function useGatewayQuotaRules(
  teamId: string,
  params?: ListQuotaRulesParams,
  options?: { enabled?: boolean }
): UseQueryResult<QuotaRule[]> {
  return useQuery({
    queryKey: gatewayQuotaRulesQueryKey(teamId, params),
    queryFn: () => gatewayApi.listQuotaRules(teamId, params),
    enabled: (options?.enabled ?? true) && teamId.length > 0,
    staleTime: GATEWAY_QUOTA_META_STALE_MS,
  })
}
