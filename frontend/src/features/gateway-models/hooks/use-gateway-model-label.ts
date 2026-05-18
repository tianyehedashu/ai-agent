import { useQuery } from '@tanstack/react-query'

import { gatewayApi } from '@/api/gateway'
import { gatewayModelsListQueryKey } from '@/features/gateway-models/utils'

/** 从团队模型列表缓存解析显示名（与 TeamModelsWorkspace 共用 queryKey，避免重复请求） */
export function useGatewayModelLabel(modelId: string, credentialId = ''): string {
  const { data: name } = useQuery({
    queryKey: gatewayModelsListQueryKey('', credentialId),
    queryFn: () =>
      gatewayApi.listModels({
        ...(credentialId ? { credential_id: credentialId } : {}),
      }),
    select: (items) => items.find((m) => m.id === modelId)?.name,
    enabled: modelId.length > 0,
    staleTime: 30_000,
  })

  return name ?? modelId
}
