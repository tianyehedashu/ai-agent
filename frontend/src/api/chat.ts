/**
 * Chat API
 */

import type { ChatEvent, Checkpoint, CheckpointDiff } from '@/types'

import { apiClient } from './client'

export interface ChatRequest {
  message: string
  sessionId?: string
  agentId?: string
}

// 转换为后端期望的格式（snake_case）
function toBackendRequest(request: ChatRequest): Record<string, unknown> {
  return {
    message: request.message,
    session_id: request.sessionId,
    agent_id: request.agentId,
  }
}

export interface ResumeRequest {
  checkpointId: string
  action: 'approve' | 'reject' | 'modify'
  modifiedArgs?: Record<string, unknown>
}

export const chatApi = {
  /**
   * 发送聊天消息 (流式，支持取消)
   */
  sendMessage(
    request: ChatRequest,
    onEvent: (event: ChatEvent) => void,
    onError?: (error: Error) => void,
    onComplete?: () => void,
    signal?: AbortSignal
  ): Promise<void> {
    return apiClient.stream(
      '/api/v1/chat',
      toBackendRequest(request),
      (event) => {
        onEvent(event as unknown as ChatEvent)
      },
      onError,
      onComplete,
      signal
    )
  },

  /**
   * 恢复执行 (流式，支持取消)
   */
  resume(
    sessionId: string,
    request: ResumeRequest,
    onEvent: (event: ChatEvent) => void,
    onError?: (error: Error) => void,
    onComplete?: () => void,
    signal?: AbortSignal
  ): Promise<void> {
    return apiClient.stream(
      '/api/v1/chat/resume',
      { sessionId, ...request },
      (event) => {
        onEvent(event as unknown as ChatEvent)
      },
      onError,
      onComplete,
      signal
    )
  },

  /**
   * 获取检查点列表
   */
  getCheckpoints(sessionId: string): Promise<Checkpoint[]> {
    return apiClient.get<Checkpoint[]>(`/api/v1/chat/checkpoints/${sessionId}`)
  },

  /**
   * 获取检查点状态
   */
  getCheckpointState(checkpointId: string): Promise<Record<string, unknown>> {
    return apiClient.get<Record<string, unknown>>(`/api/v1/chat/checkpoints/${checkpointId}/state`)
  },

  /**
   * 对比检查点
   */
  diffCheckpoints(checkpointId1: string, checkpointId2: string): Promise<CheckpointDiff> {
    return apiClient.post<CheckpointDiff>('/api/v1/chat/checkpoints/diff', {
      checkpointId1,
      checkpointId2,
    })
  },
}
