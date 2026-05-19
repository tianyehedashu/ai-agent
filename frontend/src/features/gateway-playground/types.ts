/**
 * 网关 Playground 共享类型
 */

export type PlaygroundStatus = 'idle' | 'pending' | 'streaming' | 'done' | 'error'

/** 网关兼容入口 API 风格：OpenAI Chat Completions vs Anthropic Messages */
export type PlaygroundApiFlavor = 'openai' | 'anthropic'

export interface PlaygroundMetadata {
  httpStatus?: number
  elapsedMs?: number
  promptTokens?: number
  completionTokens?: number
  totalTokens?: number
  finishReason?: string
  requestId?: string
  /** LiteLLM / 网关注入的下游费用（USD） */
  responseCostUsd?: number
}

export interface PlaygroundError {
  httpStatus?: number
  code?: string | null
  message: string
}

/** 原始响应快照：非流式为完整 JSON，流式为最后一个 chunk。 */
export type PlaygroundRawResponse = unknown
