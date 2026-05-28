/**
 * 模型列表「按凭据筛选」选项。
 *
 * 团队 Tab 使用 ``/managed-team-model-credential-filters``（注册模型绑定，成员可见凭据名）。
 */

import { useMemo } from 'react'

import { useQuery } from '@tanstack/react-query'

import { modelsApi } from '@/api/gateway/models'
import type { GatewayModelCredentialFilterOption } from '@/features/gateway-models/gateway-model-credential-filter-label'
import { fetchPlaygroundCredentialSummaries } from '@/features/gateway-playground/playground-credential-summaries'
import {
  useGatewayMemberTeamNameMap,
  useGatewayMemberTeams,
} from '@/features/gateway-teams/use-gateway-teams'

export type GatewayModelCredentialFilterScope = 'team-collaboration' | 'system'

const MODEL_CREDENTIAL_FILTER_QUERY_KEY = ['gateway', 'model-credential-filter'] as const

export function useGatewayModelCredentialFilterOptions(
  scope: GatewayModelCredentialFilterScope,
  enabled: boolean
): {
  options: GatewayModelCredentialFilterOption[]
  isLoading: boolean
} {
  const teamNameById = useGatewayMemberTeamNameMap()
  const { data: memberTeams = [], isLoading: teamsLoading } = useGatewayMemberTeams(enabled)

  const teamFiltersQuery = useQuery({
    queryKey: [...MODEL_CREDENTIAL_FILTER_QUERY_KEY, 'managed-team-registry', scope],
    queryFn: () => modelsApi.listManagedTeamModelCredentialFilters(),
    enabled: enabled && scope === 'team-collaboration',
    staleTime: 60_000,
  })

  const systemFiltersQuery = useQuery({
    queryKey: [...MODEL_CREDENTIAL_FILTER_QUERY_KEY, 'playground-system', memberTeams.length],
    queryFn: async (): Promise<GatewayModelCredentialFilterOption[]> => {
      const summaries = await fetchPlaygroundCredentialSummaries(memberTeams)
      return summaries
        .filter((cred) => cred.scope === 'system')
        .map((cred) => ({
          id: cred.id,
          name: cred.name,
          provider: cred.provider,
        }))
    },
    enabled: enabled && scope === 'system' && memberTeams.length > 0,
    staleTime: 60_000,
  })

  const options = useMemo((): GatewayModelCredentialFilterOption[] => {
    if (scope === 'system') {
      return [...(systemFiltersQuery.data ?? [])].sort((a, b) =>
        a.name.localeCompare(b.name, 'zh-CN')
      )
    }
    return (teamFiltersQuery.data?.items ?? []).map((row) => ({
      id: row.id,
      name: row.name,
      provider: row.provider,
      teamLabel: teamNameById.get(row.tenant_id),
    }))
  }, [scope, systemFiltersQuery.data, teamFiltersQuery.data?.items, teamNameById])

  const isLoading =
    teamsLoading ||
    (scope === 'team-collaboration' ? teamFiltersQuery.isLoading : systemFiltersQuery.isLoading)

  return { options, isLoading }
}

/** @deprecated 使用 {@link useGatewayModelCredentialFilterOptions}('team-collaboration', …) */
export function useManagedTeamCredentialFilterOptions(enabled: boolean): {
  options: GatewayModelCredentialFilterOption[]
  isLoading: boolean
} {
  return useGatewayModelCredentialFilterOptions('team-collaboration', enabled)
}
