/**
 * 用户 LLM 提供商配置 API
 */

import type {
  ProviderConfig,
  ProviderConfigUpdateRequest,
  ProviderTestResponse,
} from '@/types/provider-config'

import { apiClient } from './client'

export const providerConfigApi = {
  /** 获取当前用户的提供商配置列表 */
  async list(): Promise<ProviderConfig[]> {
    return apiClient.get<ProviderConfig[]>('/api/v1/settings/providers')
  },

  /** 创建或更新指定提供商的配置 */
  async update(
    provider: string,
    data: ProviderConfigUpdateRequest
  ): Promise<ProviderConfig> {
    return apiClient.put<ProviderConfig>(`/api/v1/settings/providers/${provider}`, data)
  },

  /** 删除指定提供商的配置 */
  async delete(provider: string): Promise<void> {
    return apiClient.delete<void>(`/api/v1/settings/providers/${provider}`)
  },

  /** 测试指定提供商的 Key 是否有效 */
  async test(provider: string): Promise<ProviderTestResponse> {
    return apiClient.post<ProviderTestResponse>(
      `/api/v1/settings/providers/${provider}/test`
    )
  },
}
