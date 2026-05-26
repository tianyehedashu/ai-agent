import { useEffect } from 'react'

import { useQuery } from '@tanstack/react-query'

import { gatewayApi } from '@/api/gateway'

import { applyRemoteProviderProfiles } from '../provider-profile-catalog'

/** 拉取并合并后端 provider-profiles SSOT（表单方案下拉用）。 */
export function useProviderProfilesCatalog(enabled = true): void {
  const { data } = useQuery({
    queryKey: ['gateway', 'provider-profiles'],
    queryFn: () => gatewayApi.listProviderProfiles(),
    enabled,
    staleTime: 60_000,
  })

  useEffect(() => {
    if (data && data.profiles.length > 0) {
      applyRemoteProviderProfiles(data.profiles)
    }
  }, [data])
}
