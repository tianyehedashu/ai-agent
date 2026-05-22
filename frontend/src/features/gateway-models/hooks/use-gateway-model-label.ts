import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'

import { gatewayApi } from '@/api/gateway'
import { parseScopeTab } from '@/features/gateway-models/constants'
import {
  gatewayModelsListQueryKey,
  resolveTeamModelsRegistryScope,
} from '@/features/gateway-models/utils'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useGatewayTeamId } from '@/hooks/use-gateway-team-id'

/** 从团队模型列表缓存解析显示名（与 TeamModelsWorkspace / TeamModelDetailPane 共用 queryKey） */
export function useGatewayModelLabel(modelId: string, credentialId = ''): string {
  const teamId = useGatewayTeamId()
  const { isPlatformAdmin } = useGatewayPermission()
  const [searchParams] = useSearchParams()
  const scopeTab = parseScopeTab(searchParams.get('tab'), { allowSystem: isPlatformAdmin })
  const listMode = scopeTab === 'system' ? 'system' : 'team'
  const registryScope = resolveTeamModelsRegistryScope(listMode, credentialId)
  const { data: name } = useQuery({
    queryKey: gatewayModelsListQueryKey(teamId, registryScope, '', credentialId),
    queryFn: () =>
      gatewayApi.listModels(teamId, {
        registry_scope: registryScope,
        ...(credentialId ? { credential_id: credentialId } : {}),
      }),
    select: (items) => items.find((m) => m.id === modelId)?.name,
    enabled: modelId.length > 0,
    staleTime: 30_000,
  })

  return name ?? modelId
}
