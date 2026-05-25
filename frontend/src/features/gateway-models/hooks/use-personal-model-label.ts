import { useQuery } from '@tanstack/react-query'

import { gatewayApi } from '@/api/gateway'

/** 从 GET /my-models/{id} 解析显示名 */
export function usePersonalModelLabel(modelId: string): string {
  const { data } = useQuery({
    queryKey: ['gateway', 'my-models', modelId, 'label'],
    queryFn: () => gatewayApi.getMyModel(modelId),
    select: (model) => model.display_name,
    enabled: modelId !== '',
    staleTime: 60_000,
    retry: false,
  })

  if (data) return data
  if (modelId.length > 12) return `${modelId.slice(0, 8)}…`
  return modelId || '模型'
}
