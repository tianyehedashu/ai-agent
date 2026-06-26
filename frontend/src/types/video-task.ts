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

/** 视频生成模型（网关 model_type=video 的模型 ID） */
export type VideoModel = string

/** 视频时长（秒）；允许值由后端 /video-tasks/models 的 durations 决定 */
export type VideoDuration = number

export interface VideoCatalogModelOption {
  value: string
  label: string
  durations: number[]
  maxReferenceImages: number
  supportsImageToVideo: boolean
  source: string
}

export interface VideoGenTask {
  id: string
  userId?: string
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
// Prompt Optimization Types
// ============================================

export interface VideoPromptOptimizeInput {
  userText?: string
  imageUrls?: string[]
  systemPrompt?: string
  marketplace?: string
}

export interface VideoPromptOptimizeResult {
  optimizedPrompt: string
}

export interface VideoPromptTemplate {
  systemPrompt: string
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
