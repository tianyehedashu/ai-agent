/**
 * 跨团队模型筛选：当前 actor 可见的团队凭据选项（managed-team-credentials）。
 */

import { useMemo } from 'react'

import { useQuery } from '@tanstack/react-query'

import { fetchAllManagedTeamCredentials } from '@/api/gateway/credentials'
import type { GatewayModelCredentialFilterOption } from '@/features/gateway-models/gateway-model-credential-filter-select'
import { useGatewayMemberTeamNameMap } from '@/features/gateway-teams/use-gateway-teams'

export function useManagedTeamCredentialFilterOptions(enabled: boolean): {
  options: GatewayModelCredentialFilterOption[]
  isLoading: boolean
} {
  const teamNameById = useGatewayMemberTeamNameMap()

  const { data: items = [], isLoading } = useQuery({
    queryKey: ['gateway', 'managed-team-credentials', 'filter-options'],
    queryFn: () => fetchAllManagedTeamCredentials(),
    enabled,
    staleTime: 60_000,
  })

  const options = useMemo((): GatewayModelCredentialFilterOption[] => {
    return items
      .map((cred) => ({
        id: cred.id,
        name: cred.name,
        provider: cred.provider,
        teamLabel: cred.tenant_id ? teamNameById.get(cred.tenant_id) : undefined,
      }))
      .sort((a, b) => optionLabelForSort(a).localeCompare(optionLabelForSort(b), 'zh-CN'))
  }, [items, teamNameById])

  return { options, isLoading }
}

function optionLabelForSort(option: GatewayModelCredentialFilterOption): string {
  return `${option.teamLabel ?? ''}\0${option.name}`
}
