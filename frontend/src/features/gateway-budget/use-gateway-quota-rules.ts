import { useQuery, type UseQueryResult } from '@tanstack/react-query'

import { gatewayApi } from '@/api/gateway'
import type { ListQuotaRulesParams, QuotaRule } from '@/api/gateway/quota-rules'

/** 配额规则与标签元数据缓存 60s，避免切换筛选时重复请求。 */
export const GATEWAY_QUOTA_META_STALE_MS = 60_000

export function gatewayQuotaRulesQueryKey(
  teamId: string,
  params?: ListQuotaRulesParams
): readonly ['gateway-quota-rules', string, ListQuotaRulesParams | undefined] {
  return ['gateway-quota-rules', teamId, params]
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
