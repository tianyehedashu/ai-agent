/**
 * Frontend Type Definitions
 */

// ============================================
// User Types
// ============================================

export interface User {
  id: string
  email: string
  name: string
  avatar?: string
  createdAt: string
}

// ============================================
// Agent Types
// ============================================

export interface Agent {
  id: string
  name: string
  description?: string
  systemPrompt: string
  model: string
  tools: string[]
  temperature: number
  maxTokens: number
  maxIterations: number
  isActive: boolean
  createdAt: string
  updatedAt: string
}

export interface AgentCreateInput {
  name: string
  description?: string
  systemPrompt: string
  model?: string
  tools?: string[]
  temperature?: number
  maxTokens?: number
  maxIterations?: number
}

// ============================================
// Session Types
// ============================================

export interface Session {
  id: string
  title?: string
  agentId?: string
  messageCount: number
  tokenCount: number
  createdAt: string
  updatedAt: string
}

// ============================================
// Message Types
// ============================================

export type MessageRole = 'user' | 'assistant' | 'system' | 'tool'

export interface ToolCall {
  id: string
  name: string
  arguments: Record<string, unknown>
}

export interface Message {
  id: string
  role: MessageRole
  content?: string
  toolCalls?: ToolCall[]
  toolCallId?: string
  metadata?: Record<string, unknown>
  createdAt: string
}

// ============================================
// Process Timeline Types
// ============================================

export type ProcessEventKind =
  | 'thinking'
  | 'text'
  | 'tool_call'
  | 'tool_result'
  | 'done'
  | 'error'
  | 'interrupt'

export interface ProcessEvent {
  id: string
  kind: ProcessEventKind
  timestamp: string
  payload: Record<string, unknown>
}

// ============================================
// Chat Event Types
// ============================================

export type ChatEventType =
  | 'session_created'
  | 'session_recreated'
  | 'title_updated'
  | 'thinking'
  | 'text'
  | 'tool_call'
  | 'tool_result'
  | 'interrupt'
  | 'done'
  | 'error'
  | 'terminated'

export interface ChatEvent {
  type: ChatEventType
  data: Record<string, unknown>
  timestamp: string
}

export interface ThinkingEventData {
  iteration: number
  status: string
}

export interface TextEventData {
  content: string
}

export interface ToolCallEventData {
  id: string
  name: string
  arguments: Record<string, unknown>
}

export interface ToolResultEventData {
  toolCallId: string
  success: boolean
  output: string
  error?: string
}

export interface InterruptEventData {
  checkpointId: string
  pendingAction: ToolCallEventData
  reason: string
}

export interface DoneEventData {
  content: string
  totalTokens: number
  iterations: number
}

export interface ErrorEventData {
  error: string
}

// ============================================
// Session Recreation Types
// ============================================

/** 会话历史信息（会话被清理前保存的状态） */
export interface SessionHistory {
  sessionId: string
  cleanedAt: string
  cleanupReason: string
  packagesInstalled: string[]
  filesCreated: string[]
  commandCount: number
  totalDurationMs: number
}

/** 会话重建事件数据 */
export interface SessionRecreationData {
  sessionId: string
  isNew: boolean
  isRecreated: boolean
  previousState: SessionHistory | null
  message: string | null
}

// ============================================
// Checkpoint Types
// ============================================

export interface Checkpoint {
  id: string
  sessionId: string
  step: number
  createdAt: string
  iteration?: number
  totalTokens?: number
  completed?: boolean
}

export interface CheckpointDiff {
  messagesAdded: number
  tokensDelta: number
  iterationDelta: number
}

// ============================================
// Tool Types
// ============================================

export interface Tool {
  name: string
  description: string
  category: string
  parameters: Record<string, unknown>
  requiresConfirmation: boolean
}

// ============================================
// API Response Types
// ============================================

export interface ApiResponse<T> {
  success: boolean
  data?: T
  error?: string
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  pageSize: number
  hasMore: boolean
}
