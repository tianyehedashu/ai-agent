/**
 * Memory API - 记忆管理接口
 */

import { apiV1Path } from '@/api/paths'
import type { PaginatedList } from '@/types'

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
  async list(page = 1, pageSize = 20, typeFilter?: string): Promise<PaginatedList<Memory>> {
    const items = await apiClient.get<Memory[]>(apiV1Path('/memory/'), {
      skip: (page - 1) * pageSize,
      limit: pageSize,
      type_filter: typeFilter,
    })
    return {
      items,
      total: items.length,
      page,
      page_size: pageSize,
      has_next: items.length === pageSize,
      has_prev: page > 1,
    }
  },

  /**
   * 搜索记忆
   */
  search(request: MemorySearchRequest): Promise<Memory[]> {
    return apiClient.post<Memory[]>(apiV1Path('/memory/search'), {
      query: request.query,
      top_k: request.topK ?? 10,
      type_filter: request.typeFilter,
    })
  },

  /**
   * 创建记忆
   */
  create(data: MemoryCreateRequest): Promise<Memory> {
    return apiClient.post<Memory>(apiV1Path('/memory/'), {
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
    await apiClient.delete<Record<string, never>>(apiV1Path(`/memory/${id}`))
  },
}
