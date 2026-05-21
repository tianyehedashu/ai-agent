import { apiClient } from '@/api/client'
import { apiV1Path } from '@/api/paths'

const PREFIX = apiV1Path('/admin/storage')

export interface StorageConfigAdmin {
  storage_type: string
  local_storage_path: string | null
  local_serve_prefix: string | null
  s3_bucket: string | null
  s3_region: string | null
  s3_endpoint_url: string | null
  s3_access_key: string | null
  s3_public_base_url: string | null
  image_upload_max_bytes: number
  public_access: boolean
  is_active: boolean
  secret_configured: boolean
  updated_at: string | null
}

export interface UpdateStorageConfigPayload {
  storage_type: string
  local_storage_path?: string | null
  local_serve_prefix?: string | null
  s3_bucket?: string | null
  s3_region?: string | null
  s3_endpoint_url?: string | null
  s3_access_key?: string | null
  s3_secret_key?: string | null
  s3_public_base_url?: string | null
  image_upload_max_bytes?: number
  public_access?: boolean
  is_active?: boolean
}

export interface StorageTestResult {
  status: string
  message: string
}

export const adminStorageApi = {
  async get(): Promise<StorageConfigAdmin> {
    return apiClient.get<StorageConfigAdmin>(PREFIX)
  },

  async update(payload: UpdateStorageConfigPayload): Promise<StorageConfigAdmin> {
    return apiClient.put<StorageConfigAdmin>(PREFIX, payload)
  },

  async testConnection(): Promise<StorageTestResult> {
    return apiClient.post<StorageTestResult>(`${PREFIX}/test`, {})
  },
}
