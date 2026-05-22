/**
 * AI Gateway · 系统级可见性 ACL（PlatformAdmin）
 */

import { apiClient } from '@/api/client'

import { GATEWAY_API_BASE } from './_base'

export type SystemVisibility = 'public' | 'restricted'
export type SystemModelVisibility = 'inherit' | 'public' | 'restricted'

export interface SystemCredentialSummary {
  id: string
  provider: string
  name: string
  visibility: SystemVisibility
}

export interface SystemGatewayGrant {
  id: string
  subject_kind: 'credential' | 'model'
  subject_id: string
  target_kind: 'team' | 'user'
  target_id: string
  enabled: boolean
  note: string | null
  granted_by: string
  created_at: string
  updated_at: string
}

export interface SystemGatewayGrantCreateBody {
  subject_kind: 'credential' | 'model'
  subject_id: string
  target_kind: 'team' | 'user'
  target_id: string
  note?: string | null
}

export interface SystemVisibilityTargetSnapshot {
  target_kind: 'team' | 'user'
  target_id: string
  grants: SystemGatewayGrant[]
  visible_model_names: string[]
}

const SYSTEM_BASE = `${GATEWAY_API_BASE}/system`
const ADMIN_BASE = `${GATEWAY_API_BASE}/admin`

export const systemVisibilityApi = {
  patchCredentialVisibility: (credentialId: string, visibility: SystemVisibility) =>
    apiClient.patch<{ id: string; visibility: string }>(
      `${SYSTEM_BASE}/credentials/${credentialId}/visibility`,
      { visibility }
    ),

  patchModelVisibility: (modelId: string, visibility: SystemModelVisibility) =>
    apiClient.patch<{ id: string; visibility: string }>(
      `${SYSTEM_BASE}/models/${modelId}/visibility`,
      { visibility }
    ),

  listCredentialGrants: (credentialId: string) =>
    apiClient.get<SystemGatewayGrant[]>(`${SYSTEM_BASE}/credentials/${credentialId}/grants`),

  listModelGrants: (modelId: string) =>
    apiClient.get<SystemGatewayGrant[]>(`${SYSTEM_BASE}/models/${modelId}/grants`),

  createGrant: (body: SystemGatewayGrantCreateBody) =>
    apiClient.post<SystemGatewayGrant>(`${SYSTEM_BASE}/grants`, body),

  updateGrant: (grantId: string, body: { enabled?: boolean; note?: string | null }) =>
    apiClient.patch<SystemGatewayGrant>(`${SYSTEM_BASE}/grants/${grantId}`, body),

  deleteGrant: (grantId: string) => apiClient.delete<unknown>(`${SYSTEM_BASE}/grants/${grantId}`),

  teamSystemVisibility: (teamId: string) =>
    apiClient.get<SystemVisibilityTargetSnapshot>(
      `${ADMIN_BASE}/teams/${teamId}/system-visibility`
    ),

  userSystemVisibility: (userId: string) =>
    apiClient.get<SystemVisibilityTargetSnapshot>(
      `${ADMIN_BASE}/users/${userId}/system-visibility`
    ),
} as const
