import { apiClient } from '@/api/client'
import { apiV1Path } from '@/api/paths'
import type { PaginatedList } from '@/types'

const PREFIX = apiV1Path('/admin/users')

export type PlatformRole = 'admin' | 'user' | 'viewer'

export interface PlatformUserSummary {
  id: string
  email: string
  name: string | null
  role: PlatformRole
  is_active: boolean
  is_verified: boolean
  status: string
  created_at: string
  vendor_creator_id: number | null
  avatar_url: string | null
}

export type PlatformUserListResponse = PaginatedList<PlatformUserSummary>

export interface PlatformUserListParams {
  search?: string
  role?: PlatformRole
  is_active?: boolean
  page: number
  page_size: number
}

export interface AdminUpdatePlatformUserPayload {
  name?: string | null
  avatar_url?: string | null
  vendor_creator_id?: number | null
  is_active?: boolean
}

export const adminUsersApi = {
  async list(params: PlatformUserListParams): Promise<PlatformUserListResponse> {
    return apiClient.get<PlatformUserListResponse>(PREFIX, {
      search: params.search,
      role: params.role,
      is_active: params.is_active,
      page: params.page,
      page_size: params.page_size,
    })
  },

  async getById(userId: string): Promise<PlatformUserSummary> {
    return apiClient.get<PlatformUserSummary>(`${PREFIX}/${userId}`)
  },

  async update(
    userId: string,
    payload: AdminUpdatePlatformUserPayload
  ): Promise<PlatformUserSummary> {
    return apiClient.patch<PlatformUserSummary>(`${PREFIX}/${userId}`, payload)
  },

  async lookupByEmail(email: string): Promise<PlatformUserSummary> {
    return apiClient.get<PlatformUserSummary>(`${PREFIX}/lookup`, { email })
  },

  async setPlatformRole(userId: string, role: PlatformRole): Promise<PlatformUserSummary> {
    return apiClient.patch<PlatformUserSummary>(`${PREFIX}/${userId}/role`, { role })
  },
}
