/**
 * Video Task Types - 视频生成任务类型定义
 */

// ============================================
// Task Status
// ============================================

export type VideoTaskStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'

// ============================================
// Video Task Types
// ============================================

/** 视频生成模型 */
export type VideoModel = 'openai::sora1.0' | 'openai::sora2.0'

/** 视频时长（秒） */
export type VideoDuration = 5 | 10 | 15 | 20

export interface VideoGenTask {
  id: string
  userId?: string
  anonymousUserId?: string
  sessionId?: string
  workflowId?: string
  runId?: string
  status: VideoTaskStatus
  promptText?: string
  promptSource?: string
  referenceImages: string[]
  marketplace: string
  model: VideoModel
  duration: VideoDuration
  result?: Record<string, unknown>
  errorMessage?: string
  videoUrl?: string
  createdAt: string
  updatedAt: string
}

export interface VideoTaskCreateInput {
  sessionId?: string
  promptText?: string
  promptSource?: string
  referenceImages?: string[]
  marketplace?: string
  model?: VideoModel
  duration?: VideoDuration
  autoSubmit?: boolean
}

export interface VideoTaskUpdateInput {
  promptText?: string
  promptSource?: string
  referenceImages?: string[]
  marketplace?: string
  model?: VideoModel
  duration?: VideoDuration
}

// ============================================
// API Response Types
// ============================================

export interface VideoTaskListResponse {
  items: VideoGenTask[]
  total: number
  skip: number
  limit: number
}
