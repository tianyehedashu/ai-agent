/**
 * GET /api/v1/gateway/provider-profiles — 上游方案 SSOT
 */

import { apiClient } from '@/api/client'

import { GATEWAY_API_BASE } from './_base'

export interface ProviderProfileApiBases {
  openai_compat: string | null
  anthropic_native: string | null
}

export interface ProviderProfileItem {
  id: string
  provider: string
  label: string
  api_bases: ProviderProfileApiBases
  models_list_path: string
  default_call_shape: string
  probe_strategy: string
  probe_protocol: string
  probe_supported: boolean
}

export interface ProviderProfilesListResponse {
  profiles: ProviderProfileItem[]
}

export const providerProfilesApi = {
  listProviderProfiles: async (): Promise<ProviderProfilesListResponse> => {
    return apiClient.get<ProviderProfilesListResponse>(`${GATEWAY_API_BASE}/provider-profiles`)
  },
}
