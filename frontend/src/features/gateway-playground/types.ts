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

/** 试调最近一次 POST 的请求快照（Key 已脱敏），供 UI「请求」Tab 展示。 */
export interface PlaygroundRequestSnapshot {
  method: 'POST'
  url: string
  headers: Record<string, string>
  body: Record<string, unknown>
}

/**
 * 原始响应快照：非流式为完整 JSON；
 * OpenAI 流式为 `{ type: 'openai.stream.summary', text, lastChunk }`；
 * Anthropic 流式为 `{ type: 'anthropic.stream.summary', ... }`；
 * 图片试调为 `{ type: 'image_gen', items }`；视频为 `{ type: 'video_gen', url? }`。
 */
export type PlaygroundRawResponse = unknown

export interface PlaygroundImageMediaItem {
  url?: string
  b64Json?: string
  revisedPrompt?: string
}

export interface PlaygroundImageRawSummary {
  type: 'image_gen'
  items: PlaygroundImageMediaItem[]
}

export interface PlaygroundVideoRawSummary {
  type: 'video_gen'
  url?: string
}
