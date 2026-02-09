/**
 * Video Task API - 视频生成任务 API
 */

import type {
  VideoGenTask,
  VideoTaskCreateInput,
  VideoTaskUpdateInput,
  VideoTaskListResponse,
  VideoTaskStatus,
  VideoModel,
  VideoDuration,
} from '@/types/video-task'

import { apiClient } from './client'

// ============================================
// Backend Types (snake_case)
// ============================================

interface BackendVideoTask {
  id: string
  user_id: string | null
  anonymous_user_id: string | null
  session_id: string | null
  workflow_id: string | null
  run_id: string | null
  status: string
  prompt_text: string | null
  prompt_source: string | null
  reference_images: string[]
  marketplace: string
  model: string
  duration: number
  result: Record<string, unknown> | null
  error_message: string | null
  video_url: string | null
  created_at: string
  updated_at: string
}

interface BackendVideoTaskListResponse {
  items: BackendVideoTask[]
  total: number
  skip: number
  limit: number
}

// ============================================
// Converters
// ============================================

/**
 * 将后端格式转换为前端格式（camelCase）
 */
function toFrontendVideoTask(backend: BackendVideoTask): VideoGenTask {
  return {
    id: backend.id,
    userId: backend.user_id ?? undefined,
    anonymousUserId: backend.anonymous_user_id ?? undefined,
    sessionId: backend.session_id ?? undefined,
    workflowId: backend.workflow_id ?? undefined,
    runId: backend.run_id ?? undefined,
    status: backend.status as VideoTaskStatus,
    promptText: backend.prompt_text ?? undefined,
    promptSource: backend.prompt_source ?? undefined,
    referenceImages: backend.reference_images,
    marketplace: backend.marketplace,
    model: backend.model as VideoModel,
    duration: backend.duration as VideoDuration,
    result: backend.result ?? undefined,
    errorMessage: backend.error_message ?? undefined,
    videoUrl: backend.video_url ?? undefined,
    createdAt: backend.created_at,
    updatedAt: backend.updated_at,
  }
}

/**
 * 转换为后端期望的格式（snake_case）
 */
function toBackendCreateRequest(data: VideoTaskCreateInput): Record<string, unknown> {
  return {
    session_id: data.sessionId,
    prompt_text: data.promptText,
    prompt_source: data.promptSource,
    reference_images: data.referenceImages ?? [],
    marketplace: data.marketplace ?? 'jp',
    model: data.model ?? 'openai::sora1.0',
    duration: data.duration ?? 5,
    auto_submit: data.autoSubmit ?? false,
  }
}

function toBackendUpdateRequest(data: VideoTaskUpdateInput): Record<string, unknown> {
  const result: Record<string, unknown> = {}
  if (data.promptText !== undefined) result.prompt_text = data.promptText
  if (data.promptSource !== undefined) result.prompt_source = data.promptSource
  if (data.referenceImages !== undefined) result.reference_images = data.referenceImages
  if (data.marketplace !== undefined) result.marketplace = data.marketplace
  if (data.model !== undefined) result.model = data.model
  if (data.duration !== undefined) result.duration = data.duration
  return result
}

// ============================================
// API Functions
// ============================================

export const videoTaskApi = {
  /**
   * 获取视频任务列表
   */
  async list(options?: {
    skip?: number
    limit?: number
    status?: VideoTaskStatus
    sessionId?: string
  }): Promise<VideoTaskListResponse> {
    const params: Record<string, string | number | boolean | undefined> = {}
    if (options?.skip !== undefined) params.skip = options.skip
    if (options?.limit !== undefined) params.limit = options.limit
    if (options?.status) params.status = options.status
    if (options?.sessionId) params.session_id = options.sessionId

    const backend = await apiClient.get<BackendVideoTaskListResponse>(
      '/api/v1/video-tasks/',
      params
    )

    return {
      items: backend.items.map(toFrontendVideoTask),
      total: backend.total,
      skip: backend.skip,
      limit: backend.limit,
    }
  },

  /**
   * 获取单个视频任务
   */
  async get(id: string): Promise<VideoGenTask> {
    const backend = await apiClient.get<BackendVideoTask>(`/api/v1/video-tasks/${id}`)
    return toFrontendVideoTask(backend)
  },

  /**
   * 创建视频任务
   */
  async create(data: VideoTaskCreateInput): Promise<VideoGenTask> {
    const backend = await apiClient.post<BackendVideoTask>(
      '/api/v1/video-tasks/',
      toBackendCreateRequest(data)
    )
    return toFrontendVideoTask(backend)
  },

  /**
   * 更新视频任务
   */
  async update(id: string, data: VideoTaskUpdateInput): Promise<VideoGenTask> {
    const backend = await apiClient.patch<BackendVideoTask>(
      `/api/v1/video-tasks/${id}`,
      toBackendUpdateRequest(data)
    )
    return toFrontendVideoTask(backend)
  },

  /**
   * 提交视频任务到厂商
   */
  async submit(id: string): Promise<VideoGenTask> {
    const backend = await apiClient.post<BackendVideoTask>(`/api/v1/video-tasks/${id}/submit`)
    return toFrontendVideoTask(backend)
  },

  /**
   * 轮询视频任务状态
   */
  async poll(id: string, once = true): Promise<VideoGenTask> {
    const queryParam = once ? '?once=true' : ''
    const backend = await apiClient.post<BackendVideoTask>(
      `/api/v1/video-tasks/${id}/poll${queryParam}`
    )
    return toFrontendVideoTask(backend)
  },

  /**
   * 取消视频任务
   */
  async cancel(id: string): Promise<VideoGenTask> {
    const backend = await apiClient.post<BackendVideoTask>(`/api/v1/video-tasks/${id}/cancel`)
    return toFrontendVideoTask(backend)
  },

  /**
   * 重试失败或已取消的视频任务
   *
   * 将任务重置为 pending 状态并重新提交到厂商。
   * 仅支持 failed 或 cancelled 状态的任务。
   */
  async retry(id: string): Promise<VideoGenTask> {
    const backend = await apiClient.post<BackendVideoTask>(`/api/v1/video-tasks/${id}/retry`)
    return toFrontendVideoTask(backend)
  },

  /**
   * 删除视频任务
   */
  async delete(id: string): Promise<void> {
    await apiClient.delete<Record<string, never>>(`/api/v1/video-tasks/${id}`)
  },
}
