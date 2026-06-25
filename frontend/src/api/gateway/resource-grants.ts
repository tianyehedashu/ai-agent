import { apiClient } from '@/api/client'

import { GATEWAY_API_BASE, teamGatewayPath } from './_base'

export interface ResourceGrant {
  id: string
  owner_user_id: string
  subject_kind: 'credential' | 'model'
  subject_id: string
  target_team_id: string
  enabled: boolean
  note: string | null
  granted_by: string
}

export interface ResourceGrantCreateBody {
  subject_kind: 'credential' | 'model'
  subject_id: string
  target_team_ids: string[]
  note?: string | null
}

export interface GrantedModel {
  model_id: string
  name: string
  real_model: string
  provider: string
  capability: string
  credential_id: string
  owner_user_id: string
  personal_team_id: string
}

export const resourceGrantsApi = {
  listMine: () => apiClient.get<ResourceGrant[]>(`${GATEWAY_API_BASE}/resource-grants`),

  create: (body: ResourceGrantCreateBody) =>
    apiClient.post<ResourceGrant[]>(`${GATEWAY_API_BASE}/resource-grants`, body),

  revoke: (grantId: string) =>
    apiClient.delete<unknown>(`${GATEWAY_API_BASE}/resource-grants/${grantId}`),

  listTeamGrantedModels: (teamId: string) =>
    apiClient.get<GrantedModel[]>(teamGatewayPath(teamId, '/granted-resources/models')),
}
