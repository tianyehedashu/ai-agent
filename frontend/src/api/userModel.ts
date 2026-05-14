/**
 * User Model API - 用户模型管理 API
 */

import type {
  UserModel,
  ModelType,
  AvailableModelsResponse,
  CreateUserModelBody,
  UpdateUserModelBody,
  TestConnectionResult,
} from '@/types/user-model'

import { apiClient } from './client'

const PREFIX = '/api/v1/user-models'

export const userModelApi = {
  /** 创建用户模型 */
  async create(body: CreateUserModelBody): Promise<UserModel> {
    return apiClient.post<UserModel>(PREFIX, body)
  },

  /** 用户模型列表 */
  async list(params?: {
    type?: ModelType
    provider?: string
    skip?: number
    limit?: number
  }): Promise<{ items: UserModel[]; total: number }> {
    const search: Record<string, string | number> = {}
    if (params?.type) search.type = params.type
    if (params?.provider) search.provider = params.provider
    if (params?.skip !== undefined) search.skip = params.skip
    if (params?.limit !== undefined) search.limit = params.limit
    return apiClient.get(PREFIX, search)
  },

  /** 可用模型列表（系统 + 用户合并） */
  async listAvailable(type?: ModelType, provider?: string): Promise<AvailableModelsResponse> {
    const search: Record<string, string> = {}
    if (type) search.type = type
    if (provider) search.provider = provider
    return apiClient.get<AvailableModelsResponse>(`${PREFIX}/available`, search)
  },

  /** 模型详情 */
  async get(id: string): Promise<UserModel> {
    return apiClient.get<UserModel>(`${PREFIX}/${id}`)
  },

  /** 更新模型 */
  async update(id: string, body: UpdateUserModelBody): Promise<UserModel> {
    return apiClient.patch<UserModel>(`${PREFIX}/${id}`, body)
  },

  /** 删除模型 */
  async delete(id: string): Promise<void> {
    return apiClient.delete(`${PREFIX}/${id}`)
  },

  /** 测试连接 */
  async testConnection(id: string): Promise<TestConnectionResult> {
    return apiClient.post<TestConnectionResult>(`${PREFIX}/${id}/test`, {})
  },
}
