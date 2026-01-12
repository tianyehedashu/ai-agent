/**
 * Session API
 */

import { apiClient } from './client'
import type { Session, Message, PaginatedResponse } from '@/types'

export const sessionApi = {
  /**
   * 获取会话列表
   */
  list(page = 1, pageSize = 20): Promise<PaginatedResponse<Session>> {
    return apiClient.get<PaginatedResponse<Session>>('/api/v1/sessions', {
      skip: (page - 1) * pageSize,
      limit: pageSize,
    })
  },

  /**
   * 获取单个会话
   */
  get(id: string): Promise<Session> {
    return apiClient.get<Session>(`/api/v1/sessions/${id}`)
  },

  /**
   * 创建会话
   */
  create(agentId?: string): Promise<Session> {
    return apiClient.post<Session>('/api/v1/sessions', { agentId })
  },

  /**
   * 更新会话
   */
  update(id: string, data: Partial<Session>): Promise<Session> {
    return apiClient.put<Session>(`/api/v1/sessions/${id}`, data)
  },

  /**
   * 删除会话
   */
  delete(id: string): Promise<void> {
    return apiClient.delete<void>(`/api/v1/sessions/${id}`)
  },

  /**
   * 获取会话消息
   */
  getMessages(sessionId: string, page = 1, pageSize = 50): Promise<Message[]> {
    return apiClient.get<Message[]>(`/api/v1/sessions/${sessionId}/messages`, {
      skip: (page - 1) * pageSize,
      limit: pageSize,
    })
  },
}
