/**
 * 网关调用试调 hook：直接 POST 到 OpenAI 兼容 (/v1/chat/completions)
 * 或 Anthropic 兼容 (/v1/messages) 端点。
 *
 * - 同源调用，使用 Bearer / x-api-key 虚拟 Key
 * - 支持流式（SSE）与非流式
 * - 暴露 status / content / metadata / error / rawResponse，便于 UI 增量展示
 */

import { startTransition, useCallback, useEffect, useRef, useState } from 'react'

import {
  extractAnthropicError,
  parseAnthropicSseBuffer,
  pickAnthropicText,
  type AnthropicErrorEnvelope,
  type AnthropicMessage,
  type AnthropicSseEvent,
} from './anthropic-sse'
import {
  extractOpenAiCompatError,
  extractResponseCostUsd,
  parseOpenAiSseBuffer,
  type OpenAiCompatChunk,
} from './openai-sse'

import type {
  PlaygroundApiFlavor,
  PlaygroundError,
  PlaygroundMetadata,
  PlaygroundRawResponse,
  PlaygroundStatus,
} from './types'

export type {
  PlaygroundApiFlavor,
  PlaygroundError,
  PlaygroundMetadata,
  PlaygroundRawResponse,
  PlaygroundStatus,
} from './types'

interface CallParams {
  baseUrl: string
  apiKey: string
  model: string
  prompt: string
  stream: boolean
  flavor: PlaygroundApiFlavor
  /** Anthropic 必须；OpenAI 可选 */
  maxTokens?: number
}

interface UsePlaygroundCallReturn {
  status: PlaygroundStatus
  content: string
  metadata: PlaygroundMetadata | null
  error: PlaygroundError | null
  rawResponse: PlaygroundRawResponse
  isRunning: boolean
  send: (params: CallParams) => Promise<void>
  cancel: () => void
  reset: () => void
}

const DEFAULT_ANTHROPIC_MAX_TOKENS = 1024

export function usePlaygroundCall(): UsePlaygroundCallReturn {
  const [status, setStatus] = useState<PlaygroundStatus>('idle')
  const [content, setContent] = useState('')
  const [metadata, setMetadata] = useState<PlaygroundMetadata | null>(null)
  const [error, setError] = useState<PlaygroundError | null>(null)
  const [rawResponse, setRawResponse] = useState<PlaygroundRawResponse>(null)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    return () => {
      abortRef.current?.abort()
    }
  }, [])

  const reset = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    setStatus('idle')
    setContent('')
    setMetadata(null)
    setError(null)
    setRawResponse(null)
  }, [])

  const cancel = useCallback(() => {
    abortRef.current?.abort()
  }, [])

  const send = useCallback(async (params: CallParams): Promise<void> => {
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    setStatus('pending')
    setContent('')
    setMetadata(null)
    setError(null)
    setRawResponse(null)

    const startedAt = performance.now()
    const baseTrimmed = params.baseUrl.replace(/\/$/, '')
    const isAnthropic = params.flavor === 'anthropic'

    const url = isAnthropic ? `${baseTrimmed}/messages` : `${baseTrimmed}/chat/completions`
    const body = isAnthropic
      ? JSON.stringify({
          model: params.model,
          max_tokens: params.maxTokens ?? DEFAULT_ANTHROPIC_MAX_TOKENS,
          stream: params.stream,
          messages: [{ role: 'user', content: params.prompt }],
        })
      : JSON.stringify({
          model: params.model,
          stream: params.stream,
          messages: [{ role: 'user', content: params.prompt }],
        })
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    }
    if (isAnthropic) {
      headers['x-api-key'] = params.apiKey
      headers['anthropic-version'] = '2023-06-01'
    } else {
      headers.Authorization = `Bearer ${params.apiKey}`
    }

    let response: Response
    try {
      response = await fetch(url, {
        method: 'POST',
        headers,
        body,
        signal: controller.signal,
      })
    } catch (e) {
      if (controller.signal.aborted) {
        setStatus('idle')
        return
      }
      setStatus('error')
      setError({ message: e instanceof Error ? e.message : '网络请求失败' })
      return
    }

    const requestId =
      response.headers.get('x-request-id') ??
      response.headers.get('x-litellm-request-id') ??
      response.headers.get('request-id') ??
      undefined

    if (!response.ok) {
      let errorJson: unknown = null
      try {
        errorJson = await response.json()
      } catch {
        // 非 JSON 错误体
      }
      const fallback = `HTTP ${String(response.status)} ${response.statusText}`
      const playgroundError = isAnthropic
        ? extractAnthropicError(
            errorJson as AnthropicErrorEnvelope | null,
            response.status,
            fallback
          )
        : extractOpenAiCompatError(errorJson as OpenAiCompatChunk | null, response.status, fallback)
      setStatus('error')
      setError(playgroundError)
      setMetadata({
        httpStatus: response.status,
        elapsedMs: Math.round(performance.now() - startedAt),
        requestId,
      })
      setRawResponse(errorJson)
      return
    }

    if (!params.stream) {
      if (isAnthropic) {
        await handleAnthropicJson(response, startedAt, requestId, {
          setStatus,
          setContent,
          setMetadata,
          setError,
          setRawResponse,
        })
      } else {
        await handleOpenAiJson(response, startedAt, requestId, {
          setStatus,
          setContent,
          setMetadata,
          setError,
          setRawResponse,
        })
      }
      return
    }

    const reader = response.body?.getReader()
    if (!reader) {
      setStatus('error')
      setError({ httpStatus: response.status, message: '当前浏览器不支持流式响应' })
      return
    }

    setStatus('streaming')
    if (isAnthropic) {
      await streamAnthropic(reader, controller, response.status, startedAt, requestId, {
        setStatus,
        setContent,
        setMetadata,
        setError,
        setRawResponse,
      })
    } else {
      await streamOpenAi(reader, controller, response.status, startedAt, requestId, {
        setStatus,
        setContent,
        setMetadata,
        setError,
        setRawResponse,
      })
    }
  }, [])

  return {
    status,
    content,
    metadata,
    error,
    rawResponse,
    isRunning: status === 'pending' || status === 'streaming',
    send,
    cancel,
    reset,
  }
}

interface Setters {
  setStatus: (s: PlaygroundStatus) => void
  setContent: (s: string) => void
  setMetadata: (m: PlaygroundMetadata | null) => void
  setError: (e: PlaygroundError | null) => void
  setRawResponse: (r: PlaygroundRawResponse) => void
}

async function handleOpenAiJson(
  response: Response,
  startedAt: number,
  requestId: string | undefined,
  setters: Setters
): Promise<void> {
  let json: OpenAiCompatChunk | null = null
  try {
    json = (await response.json()) as OpenAiCompatChunk
  } catch (e) {
    setters.setStatus('error')
    setters.setError({
      httpStatus: response.status,
      message: e instanceof Error ? e.message : '响应解析失败',
    })
    return
  }
  const text = json.choices?.[0]?.message?.content ?? ''
  setters.setContent(text)
  setters.setMetadata({
    httpStatus: response.status,
    elapsedMs: Math.round(performance.now() - startedAt),
    promptTokens: json.usage?.prompt_tokens,
    completionTokens: json.usage?.completion_tokens,
    totalTokens: json.usage?.total_tokens,
    finishReason: json.choices?.[0]?.finish_reason ?? undefined,
    requestId: json.id ?? requestId,
    responseCostUsd: extractResponseCostUsd(json),
  })
  setters.setRawResponse(json)
  setters.setStatus('done')
}

async function handleAnthropicJson(
  response: Response,
  startedAt: number,
  requestId: string | undefined,
  setters: Setters
): Promise<void> {
  let json: AnthropicMessage | null = null
  try {
    json = (await response.json()) as AnthropicMessage
  } catch (e) {
    setters.setStatus('error')
    setters.setError({
      httpStatus: response.status,
      message: e instanceof Error ? e.message : '响应解析失败',
    })
    return
  }
  setters.setContent(pickAnthropicText(json))
  setters.setMetadata({
    httpStatus: response.status,
    elapsedMs: Math.round(performance.now() - startedAt),
    promptTokens: json.usage?.input_tokens,
    completionTokens: json.usage?.output_tokens,
    totalTokens:
      typeof json.usage?.input_tokens === 'number' && typeof json.usage.output_tokens === 'number'
        ? json.usage.input_tokens + json.usage.output_tokens
        : undefined,
    finishReason: json.stop_reason ?? undefined,
    requestId: json.id ?? requestId,
  })
  setters.setRawResponse(json)
  setters.setStatus('done')
}

async function streamOpenAi(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  controller: AbortController,
  httpStatus: number,
  startedAt: number,
  requestId: string | undefined,
  setters: Setters
): Promise<void> {
  const decoder = new TextDecoder('utf-8')
  let buffer = ''
  let acc = ''
  let lastJson: OpenAiCompatChunk | null = null
  try {
    let finished = false
    while (!finished) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const parsed = parseOpenAiSseBuffer(buffer)
      buffer = parsed.rest
      let deltaBatch = ''
      for (const chunk of parsed.chunks) {
        lastJson = chunk
        const delta = chunk.choices?.[0]?.delta?.content
        if (typeof delta === 'string' && delta.length > 0) {
          deltaBatch += delta
        }
      }
      if (deltaBatch.length > 0) {
        acc += deltaBatch
        const snapshot = acc
        startTransition(() => {
          setters.setContent(snapshot)
        })
      }
      if (parsed.done) finished = true
    }
  } catch (e) {
    if (controller.signal.aborted) {
      setters.setStatus('idle')
      return
    }
    setters.setStatus('error')
    setters.setError({
      httpStatus,
      message: e instanceof Error ? e.message : '流式读取失败',
    })
    return
  }

  setters.setMetadata({
    httpStatus,
    elapsedMs: Math.round(performance.now() - startedAt),
    finishReason: lastJson?.choices?.[0]?.finish_reason ?? undefined,
    promptTokens: lastJson?.usage?.prompt_tokens,
    completionTokens: lastJson?.usage?.completion_tokens,
    totalTokens: lastJson?.usage?.total_tokens,
    requestId: lastJson?.id ?? requestId,
    responseCostUsd: extractResponseCostUsd(lastJson),
  })
  setters.setRawResponse(lastJson)
  setters.setStatus('done')
}

async function streamAnthropic(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  controller: AbortController,
  httpStatus: number,
  startedAt: number,
  requestId: string | undefined,
  setters: Setters
): Promise<void> {
  const decoder = new TextDecoder('utf-8')
  let buffer = ''
  let acc = ''
  let messageId: string | undefined
  let model: string | undefined
  let stopReason: string | undefined
  let inputTokens: number | undefined
  let outputTokens: number | undefined
  let lastEvent: AnthropicSseEvent | null = null
  try {
    let finished = false
    while (!finished) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const parsed = parseAnthropicSseBuffer(buffer)
      buffer = parsed.rest
      let deltaBatch = ''
      for (const evt of parsed.events) {
        lastEvent = evt
        if (evt.type === 'message_start' && 'message' in evt && evt.message) {
          messageId = evt.message.id ?? messageId
          model = evt.message.model ?? model
          inputTokens = evt.message.usage?.input_tokens ?? inputTokens
        } else if (evt.type === 'content_block_delta' && 'delta' in evt) {
          const text = evt.delta?.text
          if (typeof text === 'string' && text.length > 0) {
            deltaBatch += text
          }
        } else if (evt.type === 'message_delta' && 'delta' in evt) {
          stopReason = evt.delta?.stop_reason ?? stopReason
          if ('usage' in evt && typeof evt.usage?.output_tokens === 'number') {
            outputTokens = evt.usage.output_tokens
          }
        }
      }
      if (deltaBatch.length > 0) {
        acc += deltaBatch
        const snapshot = acc
        startTransition(() => {
          setters.setContent(snapshot)
        })
      }
      if (parsed.done) finished = true
    }
  } catch (e) {
    if (controller.signal.aborted) {
      setters.setStatus('idle')
      return
    }
    setters.setStatus('error')
    setters.setError({
      httpStatus,
      message: e instanceof Error ? e.message : '流式读取失败',
    })
    return
  }

  const totalTokens =
    typeof inputTokens === 'number' && typeof outputTokens === 'number'
      ? inputTokens + outputTokens
      : undefined
  setters.setMetadata({
    httpStatus,
    elapsedMs: Math.round(performance.now() - startedAt),
    finishReason: stopReason,
    promptTokens: inputTokens,
    completionTokens: outputTokens,
    totalTokens,
    requestId: messageId ?? requestId,
  })
  // raw 取最后一个事件 + 累计的关键元数据（流式没有单一 JSON 终响应）
  setters.setRawResponse({
    type: 'anthropic.stream.summary',
    messageId,
    model,
    stopReason,
    usage: { input_tokens: inputTokens, output_tokens: outputTokens },
    lastEvent,
  })
  setters.setStatus('done')
}
