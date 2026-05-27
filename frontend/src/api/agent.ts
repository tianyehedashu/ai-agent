/**
 * Agent API
 */

import { apiV1Path } from '@/api/paths'
import type { Agent, AgentCreateInput, PaginatedList } from '@/types'

import { apiClient } from './client'

export const agentApi = {
  /**
   * 获取 Agent 列表
   */
  async list(page = 1, pageSize = 20): Promise<PaginatedList<Agent>> {
    const items = await apiClient.get<Agent[]>(apiV1Path('/agents/'), {
      skip: (page - 1) * pageSize,
      limit: pageSize,
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
   * 获取单个 Agent
   */
  get(id: string): Promise<Agent> {
    return apiClient.get<Agent>(apiV1Path(`/agents/${id}`))
  },

  /**
   * 创建 Agent
   */
  create(data: AgentCreateInput): Promise<Agent> {
    return apiClient.post<Agent>(apiV1Path('/agents/'), data)
  },

  /**
   * 更新 Agent
   */
  update(id: string, data: Partial<AgentCreateInput>): Promise<Agent> {
    return apiClient.put<Agent>(apiV1Path(`/agents/${id}`), data)
  },

  /**
   * 删除 Agent
   */
  async delete(id: string): Promise<void> {
    await apiClient.delete<Record<string, never>>(apiV1Path(`/agents/${id}`))
  },
}
