/**
 * API Key Management API
 *
 * API Key 管理相关的 API 客户端
 */

import type {
  ApiKey,
  ApiKeyCreateRequest,
  ApiKeyCreatedResponse,
  ApiKeyUpdateRequest,
  ApiKeyUsageLog,
  ApiKeyScope,
} from '@/types/api-key'

import { apiClient } from './client'

/**
 * API Key API 客户端
 */
export const apiKeyApi = {
  /**
   * 获取 API Key 列表
   */
  async list(options?: {
    include_expired?: boolean
    include_revoked?: boolean
    skip?: number
    limit?: number
  }): Promise<ApiKey[]> {
    return apiClient.get<ApiKey[]>('/api/v1/api-keys', options)
  },

  /**
   * 创建新的 API Key
   *
   * @param data 创建请求
   * @returns 包含完整 Key 的响应（仅此机会）
   */
  async create(data: ApiKeyCreateRequest): Promise<ApiKeyCreatedResponse> {
    return apiClient.post<ApiKeyCreatedResponse>('/api/v1/api-keys', data)
  },

  /**
   * 获取单个 API Key 详情
   */
  async get(id: string): Promise<ApiKey> {
    return apiClient.get<ApiKey>(`/api/v1/api-keys/${id}`)
  },

  /**
   * 解密并显示完整的 API Key
   *
   * @param id API Key ID
   * @returns 包含完整 API Key 的响应
   */
  async reveal(id: string): Promise<{ api_key: string }> {
    return apiClient.get<{ api_key: string }>(`/api/v1/api-keys/${id}/reveal`)
  },

  /**
   * 更新 API Key
   */
  async update(id: string, data: ApiKeyUpdateRequest): Promise<ApiKey> {
    return apiClient.put<ApiKey>(`/api/v1/api-keys/${id}`, data)
  },

  /**
   * 撤销 API Key
   */
  async revoke(id: string): Promise<void> {
    return apiClient.post<void>(`/api/v1/api-keys/${id}/revoke`)
  },

  /**
   * 删除 API Key
   */
  async delete(id: string): Promise<void> {
    return apiClient.delete<void>(`/api/v1/api-keys/${id}`)
  },

  /**
   * 获取 API Key 使用日志
   */
  async getUsageLogs(
    id: string,
    options?: { skip?: number; limit?: number }
  ): Promise<ApiKeyUsageLog[]> {
    return apiClient.get<ApiKeyUsageLog[]>(
      `/api/v1/api-keys/${id}/logs`,
      options
    )
  },

  /**
   * 获取可用的作用域列表
   */
  async getScopes(): Promise<string[]> {
    return apiClient.get<string[]>('/api/v1/api-keys/scopes/list')
  },

  /**
   * 获取预设的作用域分组
   */
  async getScopeGroups(): Promise<Record<string, string[]>> {
    return apiClient.get<Record<string, string[]>>('/api/v1/api-keys/scopes/groups')
  },
}

// 类型导出（从 types/api-key.ts 重新导出，方便集中导入）
export type {
  ApiKey,
  ApiKeyCreateRequest,
  ApiKeyCreatedResponse,
  ApiKeyScope,
  ApiKeyStatus,
  ApiKeyUpdateRequest,
  ApiKeyUsageLog,
} from '@/types/api-key'
