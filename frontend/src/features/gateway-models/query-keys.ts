import type { QueryClient } from '@tanstack/react-query'

/** 凭据关联模型列表 query key（读侧含 teamId + tab；失效时可省略 tab 前缀匹配） */
export function gatewayModelsByCredentialQueryKey(
  teamId: string,
  credentialId: string,
  modelsTab: 'shared' | 'system' = 'shared'
): readonly ['gateway', 'models', string, 'by-credential', string, 'shared' | 'system'] {
  return ['gateway', 'models', teamId, 'by-credential', credentialId, modelsTab]
}

/** 聊天/创作模型选择器（GET /models/available）React Query 前缀 */
export const GATEWAY_MODELS_AVAILABLE_QUERY_KEY = ['gateway-models-available'] as const

/** 失效全部工作区/筛选条件下的 available 列表（共享路由、个人模型变更后调用） */
export function invalidateGatewayModelsAvailableCaches(queryClient: QueryClient): void {
  void queryClient.invalidateQueries({ queryKey: GATEWAY_MODELS_AVAILABLE_QUERY_KEY })
}

/** 失效某凭据下全部 tab 的关联模型缓存（可选限定 teamId） */
export function gatewayModelsByCredentialInvalidatePrefix(
  credentialId: string,
  teamId?: string
): readonly string[] {
  if (teamId) {
    return ['gateway', 'models', teamId, 'by-credential', credentialId]
  }
  return ['gateway', 'models', 'by-credential', credentialId]
}
