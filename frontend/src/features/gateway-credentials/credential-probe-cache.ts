/**
 * 凭据上游探测结果在 react-query 中的缓存键与新鲜度判断。
 */

import type { CredentialUpstreamScope } from '@/features/gateway-credentials/types'

import type { QueryClient } from '@tanstack/react-query'

export const PROBE_CACHE_STALE_MS = 5 * 60 * 1000

export function credentialProbeCacheKey(
  scope: CredentialUpstreamScope,
  credentialId: string
): readonly ['gateway', 'credential-probe', CredentialUpstreamScope, string] {
  return ['gateway', 'credential-probe', scope, credentialId] as const
}

export function isProbeCacheFresh(queryClient: QueryClient, cacheKey: readonly unknown[]): boolean {
  const state = queryClient.getQueryState(cacheKey)
  if (state?.data === undefined) return false
  return Date.now() - state.dataUpdatedAt < PROBE_CACHE_STALE_MS
}

/** 凭据密钥 / api_base / 启用状态变更后清除，避免弹窗展示过期探测结果 */
export function invalidateCredentialProbeCache(
  queryClient: QueryClient,
  scope: CredentialUpstreamScope,
  credentialId: string
): void {
  queryClient.removeQueries({ queryKey: credentialProbeCacheKey(scope, credentialId) })
}
