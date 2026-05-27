import { useQuery } from '@tanstack/react-query'

import { gatewayApi } from '@/api/gateway'
import type { ProviderProfilesListResponse } from '@/api/gateway/provider-profiles'

import { applyRemoteProviderProfiles } from '../provider-profile-catalog'

async function fetchAndApplyProviderProfiles(): Promise<ProviderProfilesListResponse> {
  const data = await gatewayApi.listProviderProfiles()
  if (data.profiles.length > 0) {
    applyRemoteProviderProfiles(data.profiles)
  }
  return data
}

/** 拉取并合并后端 provider-profiles SSOT（表单方案下拉用）。 */
export function useProviderProfilesCatalog(enabled = true): void {
  useQuery({
    queryKey: ['gateway', 'provider-profiles'],
    queryFn: fetchAndApplyProviderProfiles,
    enabled,
    staleTime: 60_000,
  })
}
