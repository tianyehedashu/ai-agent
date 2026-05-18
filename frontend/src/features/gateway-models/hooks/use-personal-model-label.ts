import { useQuery } from '@tanstack/react-query'

import { gatewayApi } from '@/api/gateway'

/** 从个人模型列表缓存解析显示名 */
export function usePersonalModelLabel(modelId: string): string {
  const { data } = useQuery({
    queryKey: ['gateway', 'my-models'],
    queryFn: () => gatewayApi.listMyModels(),
    enabled: modelId !== '',
    staleTime: 60_000,
  })

  const match = data?.find((m) => m.id === modelId)
  if (match) return match.display_name
  if (modelId.length > 12) return `${modelId.slice(0, 8)}…`
  return modelId || '模型'
}
