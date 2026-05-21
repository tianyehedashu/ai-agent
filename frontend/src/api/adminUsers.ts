import { apiClient } from '@/api/client'

const PREFIX = '/api/v1/admin/users'

export type PlatformRole = 'admin' | 'user' | 'viewer'

export interface PlatformUserSummary {
  id: string
  email: string
  name: string | null
  role: PlatformRole
}

export const adminUsersApi = {
  async lookupByEmail(email: string): Promise<PlatformUserSummary> {
    return apiClient.get<PlatformUserSummary>(`${PREFIX}/lookup`, { email })
  },

  async setPlatformRole(userId: string, role: PlatformRole): Promise<PlatformUserSummary> {
    return apiClient.patch<PlatformUserSummary>(`${PREFIX}/${userId}/role`, { role })
  },
}
