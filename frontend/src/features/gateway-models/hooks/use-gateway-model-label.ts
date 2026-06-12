import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'

import { gatewayApi } from '@/api/gateway'
import { parseModelsScopeTab } from '@/features/gateway-models/constants'
import { gatewayModelLabel } from '@/features/gateway-models/list/gateway-model-display-name'
import { resolveTeamModelsRegistryScope } from '@/features/gateway-models/utils'
import { useGatewayTeamId } from '@/hooks/use-gateway-team-id'

/** 从 GET /models/{id} 解析显示名 */
export function useGatewayModelLabel(modelId: string, credentialId = ''): string {
  const teamId = useGatewayTeamId()
  const [searchParams] = useSearchParams()
  const scopeTab = parseModelsScopeTab(searchParams.get('tab'))
  const listMode = scopeTab === 'system' ? 'system' : 'team'
  const registryScope = resolveTeamModelsRegistryScope(listMode, credentialId)
  const { data: name } = useQuery({
    queryKey: ['gateway', 'models', teamId, modelId, registryScope, 'label'],
    queryFn: () =>
      gatewayApi.getModel(teamId, modelId, {
        registry_scope: registryScope,
      }),
    select: (model) => gatewayModelLabel(model),
    enabled: modelId.length > 0,
    staleTime: 30_000,
    retry: false,
  })

  return name ?? modelId
}
