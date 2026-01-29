/**
 * Session API
 */

import type { Session, Message, PaginatedResponse, ToolCall, MessageRole } from '@/types'

import { apiClient } from './client'

// 后端返回的Session格式（snake_case）
interface BackendSession {
  id: string
  user_id: string | null // 注册用户 ID（匿名用户为 null）
  anonymous_user_id: string | null // 匿名用户 ID（注册用户为 null）
  agent_id: string | null
  title: string | null
  status: string
  message_count: number
  token_count: number
  created_at: string
  updated_at: string
}

// 将后端格式转换为前端格式（camelCase）
function toFrontendSession(backend: BackendSession): Session {
  return {
    id: backend.id,
    title: backend.title ?? undefined,
    agentId: backend.agent_id ?? undefined,
    messageCount: backend.message_count,
    tokenCount: backend.token_count,
    createdAt: backend.created_at,
    updatedAt: backend.updated_at,
  }
}

// 转换为后端期望的格式（snake_case）
function toBackendCreateRequest(data: {
  agentId?: string
  title?: string
}): Record<string, unknown> {
  return {
    agent_id: data.agentId,
    title: data.title,
  }
}

// 后端返回的消息格式（snake_case）
interface BackendMessage {
  id: string
  session_id: string
  role: string
  content: string | null
  tool_calls: Record<string, unknown> | null
  tool_call_id: string | null
  metadata: Record<string, unknown>
  token_count: number | null
  created_at: string
}

// 将后端消息格式转换为前端格式（camelCase）
function toFrontendMessage(backend: BackendMessage): Message {
  // 转换 tool_calls：后端可能是 dict 或数组，需要转换为 ToolCall[]
  let toolCalls: ToolCall[] | undefined
  if (backend.tool_calls) {
    if (Array.isArray(backend.tool_calls)) {
      // 如果已经是数组，直接转换
      toolCalls = backend.tool_calls.map((tc: unknown) => {
        if (typeof tc === 'object' && tc !== null && 'id' in tc && 'name' in tc) {
          return {
            id: String(tc.id),
            name: String(tc.name),
            arguments: (tc as { arguments?: Record<string, unknown> }).arguments ?? {},
          }
        }
        // 兼容格式：可能是 { tool_name: ..., arguments: ... }
        const tcObj = tc as Record<string, unknown>
        const idValue = tcObj.id ?? tcObj.tool_call_id
        const nameValue = tcObj.name ?? tcObj.tool_name
        return {
          id: typeof idValue === 'string' ? idValue : '',
          name: typeof nameValue === 'string' ? nameValue : '',
          arguments: (tcObj.arguments ?? {}) as Record<string, unknown>,
        }
      })
    } else if (typeof backend.tool_calls === 'object' && !Array.isArray(backend.tool_calls)) {
      // 如果是单个对象，转换为数组
      // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition
      if (backend.tool_calls === null) {
        toolCalls = undefined
      } else {
        const tcObj = backend.tool_calls
        const idValue = tcObj.id ?? tcObj.tool_call_id
        const nameValue = tcObj.name ?? tcObj.tool_name
        toolCalls = [
          {
            id: typeof idValue === 'string' ? idValue : '',
            name: typeof nameValue === 'string' ? nameValue : '',
            arguments: (tcObj.arguments ?? {}) as Record<string, unknown>,
          },
        ]
      }
    }
  }

  return {
    id: backend.id,
    role: backend.role as MessageRole,
    content: backend.content ?? undefined,
    toolCalls,
    toolCallId: backend.tool_call_id ?? undefined,
    metadata: backend.metadata,
    createdAt: backend.created_at,
  }
}

export const sessionApi = {
  /**
   * 获取会话列表
   */
  async list(page = 1, pageSize = 20): Promise<PaginatedResponse<Session>> {
    const backendList = await apiClient.get<BackendSession[]>('/api/v1/sessions', {
      skip: (page - 1) * pageSize,
      limit: pageSize,
    })

    // 转换为前端期望的PaginatedResponse格式
    return {
      items: backendList.map(toFrontendSession),
      total: backendList.length, // 后端没有返回total，使用列表长度作为近似值
      page,
      pageSize,
      hasMore: backendList.length === pageSize, // 如果返回的数量等于pageSize，可能还有更多
    }
  },

  /**
   * 获取单个会话
   */
  async get(id: string): Promise<Session> {
    const backend = await apiClient.get<BackendSession>(`/api/v1/sessions/${id}`)
    return toFrontendSession(backend)
  },

  /**
   * 创建会话
   */
  async create(options?: { agentId?: string; title?: string }): Promise<Session> {
    const backend = await apiClient.post<BackendSession>(
      '/api/v1/sessions',
      toBackendCreateRequest(options ?? {})
    )
    return toFrontendSession(backend)
  },

  /**
   * 更新会话
   */
  async update(id: string, data: Partial<Session>): Promise<Session> {
    // 转换字段名：agentId -> agent_id
    const backendData: Record<string, unknown> = {}
    if (data.title !== undefined) backendData.title = data.title
    if (data.agentId !== undefined) backendData.agent_id = data.agentId

    const backend = await apiClient.patch<BackendSession>(`/api/v1/sessions/${id}`, backendData)
    return toFrontendSession(backend)
  },

  /**
   * 删除会话
   */
  async delete(id: string): Promise<void> {
    await apiClient.delete<Record<string, never>>(`/api/v1/sessions/${id}`)
  },

  /**
   * 获取会话消息
   */
  async getMessages(sessionId: string, page = 1, pageSize = 50): Promise<Message[]> {
    const backendList = await apiClient.get<BackendMessage[]>(
      `/api/v1/sessions/${sessionId}/messages`,
      {
        skip: (page - 1) * pageSize,
        limit: pageSize,
      }
    )
    return backendList.map(toFrontendMessage)
  },

  /**
   * 生成会话标题
   * @param sessionId 会话 ID
   * @param strategy 生成策略: 'first_message' | 'summary'
   */
  async generateTitle(
    sessionId: string,
    strategy: 'first_message' | 'summary' = 'summary'
  ): Promise<Session> {
    const backend = await apiClient.post<BackendSession>(
      `/api/v1/sessions/${sessionId}/generate-title?strategy=${strategy}`
    )
    return toFrontendSession(backend)
  },
}
