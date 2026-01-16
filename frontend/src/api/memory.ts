/**
 * Memory API - 记忆管理接口
 */

import type { PaginatedResponse } from '@/types'

import { apiClient } from './client'

export interface Memory {
  id: string
  type: 'fact' | 'episode' | 'procedure' | 'preference'
  content: string
  importance: number
  createdAt: string
  metadata: Record<string, unknown>
}

export interface MemorySearchRequest {
  query: string
  topK?: number
  typeFilter?: string
}

export interface MemoryCreateRequest {
  type: 'fact' | 'episode' | 'procedure' | 'preference'
  content: string
  importance?: number
  metadata?: Record<string, unknown>
}

export const memoryApi = {
  /**
   * 获取记忆列表
   */
  list(page = 1, pageSize = 20, typeFilter?: string): Promise<PaginatedResponse<Memory>> {
    return apiClient.get<PaginatedResponse<Memory>>('/api/v1/memory', {
      skip: (page - 1) * pageSize,
      limit: pageSize,
      type_filter: typeFilter,
    })
  },

  /**
   * 搜索记忆
   */
  search(request: MemorySearchRequest): Promise<Memory[]> {
    return apiClient.post<Memory[]>('/api/v1/memory/search', {
      query: request.query,
      top_k: request.topK ?? 10,
      type_filter: request.typeFilter,
    })
  },

  /**
   * 创建记忆
   */
  create(data: MemoryCreateRequest): Promise<Memory> {
    return apiClient.post<Memory>('/api/v1/memory', {
      type: data.type,
      content: data.content,
      importance: data.importance ?? 0.5,
      metadata: data.metadata ?? {},
    })
  },

  /**
   * 删除记忆
   */
  async delete(id: string): Promise<void> {
    await apiClient.delete<Record<string, never>>(`/api/v1/memory/${id}`)
  },
}
