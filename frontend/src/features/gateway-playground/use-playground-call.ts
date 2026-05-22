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
  extractAnthropicDeltaText,
  extractAnthropicError,
  parseAnthropicSseBuffer,
  pickAnthropicText,
  pickAnthropicThinking,
  type AnthropicErrorEnvelope,
  type AnthropicMessage,
  type AnthropicSseEvent,
} from './anthropic-sse'
import {
  extractOpenAiCompatError,
  extractOpenAiStreamTextParts,
  extractResponseCostUsd,
  parseOpenAiSseBuffer,
  type OpenAiCompatChunk,
} from './openai-sse'
import {
  buildNetworkPlaygroundError,
  extractPlaygroundHttpError,
  readPlaygroundErrorBody,
} from './playground-error'
import {
  buildPlaygroundRequestBody,
  buildVisionRequestBody,
  maskAuthHeadersForDisplay,
} from './playground-request'

import type {
  PlaygroundApiFlavor,
  PlaygroundError,
  PlaygroundMetadata,
  PlaygroundRawResponse,
  PlaygroundRequestSnapshot,
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
  /** 视觉理解：OpenAI 多模态 content */
  imageUrl?: string
  enableThinking?: boolean
  temperature?: number
}

interface UsePlaygroundCallReturn {
  status: PlaygroundStatus
  content: string
  thinkingContent: string
  metadata: PlaygroundMetadata | null
  error: PlaygroundError | null
  rawResponse: PlaygroundRawResponse
  lastRequest: PlaygroundRequestSnapshot | null
  isRunning: boolean
  send: (params: CallParams) => Promise<void>
  cancel: () => void
  reset: () => void
}

export function usePlaygroundCall(): UsePlaygroundCallReturn {
  const [status, setStatus] = useState<PlaygroundStatus>('idle')
  const [content, setContent] = useState('')
  const [thinkingContent, setThinkingContent] = useState('')
  const [metadata, setMetadata] = useState<PlaygroundMetadata | null>(null)
  const [error, setError] = useState<PlaygroundError | null>(null)
  const [rawResponse, setRawResponse] = useState<PlaygroundRawResponse>(null)
  const [lastRequest, setLastRequest] = useState<PlaygroundRequestSnapshot | null>(null)
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
    setThinkingContent('')
    setMetadata(null)
    setError(null)
    setRawResponse(null)
    setLastRequest(null)
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
    setThinkingContent('')
    setMetadata(null)
    setError(null)
    setRawResponse(null)
    setLastRequest(null)

    const startedAt = performance.now()
    const baseTrimmed = params.baseUrl.replace(/\/$/, '')
    const isAnthropic = params.flavor === 'anthropic'

    const visionUrl = params.imageUrl?.trim()
    const url = isAnthropic ? `${baseTrimmed}/messages` : `${baseTrimmed}/chat/completions`
    const bodyObject = visionUrl
      ? buildVisionRequestBody({
          model: params.model,
          prompt: params.prompt,
          imageUrl: visionUrl,
          stream: params.stream,
        })
      : buildPlaygroundRequestBody({
          model: params.model,
          prompt: params.prompt,
          stream: params.stream,
          flavor: params.flavor,
          maxTokens: params.maxTokens,
          enableThinking: params.enableThinking,
          temperature: params.temperature,
        })
    const body = JSON.stringify(bodyObject)
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    }
    if (isAnthropic) {
      headers['x-api-key'] = params.apiKey
      headers['anthropic-version'] = '2023-06-01'
    } else {
      headers.Authorization = `Bearer ${params.apiKey}`
    }

    setLastRequest({
      method: 'POST',
      url,
      headers: maskAuthHeadersForDisplay(headers),
      body: bodyObject,
    })

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
      setError(buildNetworkPlaygroundError(e, url))
      return
    }

    const requestId =
      response.headers.get('x-request-id') ??
      response.headers.get('x-litellm-request-id') ??
      response.headers.get('request-id') ??
      undefined

    if (!response.ok) {
      const errorJson = await readPlaygroundErrorBody(response)
      const fallback = `HTTP ${String(response.status)} ${response.statusText}`
      const playgroundError = extractPlaygroundHttpError(
        errorJson,
        response.status,
        fallback,
        params.flavor
      )
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
          setThinkingContent,
          setMetadata,
          setError,
          setRawResponse,
        })
      } else {
        await handleOpenAiJson(response, startedAt, requestId, {
          setStatus,
          setContent,
          setThinkingContent,
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
        setThinkingContent,
        setMetadata,
        setError,
        setRawResponse,
      })
    } else {
      await streamOpenAi(reader, controller, response.status, startedAt, requestId, {
        setStatus,
        setContent,
        setThinkingContent,
        setMetadata,
        setError,
        setRawResponse,
      })
    }
  }, [])

  return {
    status,
    content,
    thinkingContent,
    metadata,
    error,
    rawResponse,
    lastRequest,
    isRunning: status === 'pending' || status === 'streaming',
    send,
    cancel,
    reset,
  }
}

interface Setters {
  setStatus: (s: PlaygroundStatus) => void
  setContent: (s: string) => void
  setThinkingContent: (s: string) => void
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
  const message = json.choices?.[0]?.message
  const text = message?.content ?? ''
  const reasoning = typeof message?.reasoning_content === 'string' ? message.reasoning_content : ''
  setters.setThinkingContent(reasoning)
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
    hasReasoning: reasoning.length > 0,
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
  const thinking = pickAnthropicThinking(json)
  setters.setThinkingContent(thinking)
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
    hasReasoning: thinking.length > 0,
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
  let answerAcc = ''
  let thinkingAcc = ''
  let lastJson: OpenAiCompatChunk | null = null
  try {
    let finished = false
    while (!finished) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const parsed = parseOpenAiSseBuffer(buffer)
      buffer = parsed.rest
      let contentBatch = ''
      let reasoningBatch = ''
      for (const chunk of parsed.chunks) {
        if (chunk.error) {
          setters.setStatus('error')
          setters.setError(
            extractOpenAiCompatError(chunk, httpStatus, chunk.error.message ?? '流式返回错误')
          )
          return
        }
        lastJson = chunk
        const parts = extractOpenAiStreamTextParts(chunk)
        if (parts.content.length > 0) contentBatch += parts.content
        if (parts.reasoning.length > 0) reasoningBatch += parts.reasoning
      }
      if (contentBatch.length > 0 || reasoningBatch.length > 0) {
        answerAcc += contentBatch
        thinkingAcc += reasoningBatch
        const answerSnap = answerAcc
        const thinkingSnap = thinkingAcc
        startTransition(() => {
          setters.setContent(answerSnap)
          setters.setThinkingContent(thinkingSnap)
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
    hasReasoning: thinkingAcc.length > 0,
  })
  setters.setRawResponse({
    type: 'openai.stream.summary',
    text: answerAcc,
    thinkingText: thinkingAcc,
    lastChunk: lastJson,
  })
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
  let answerAcc = ''
  let thinkingAcc = ''
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
      let textBatch = ''
      let thinkingBatch = ''
      for (const evt of parsed.events) {
        lastEvent = evt
        if (evt.type === 'error' && 'error' in evt) {
          setters.setStatus('error')
          setters.setError(
            extractAnthropicError(
              evt as AnthropicErrorEnvelope,
              httpStatus,
              evt.error?.message ?? '流式返回错误'
            )
          )
          return
        }
        if (evt.type === 'message_start' && 'message' in evt && evt.message) {
          messageId = evt.message.id ?? messageId
          model = evt.message.model ?? model
          inputTokens = evt.message.usage?.input_tokens ?? inputTokens
        } else if (evt.type === 'content_block_delta') {
          const parts = extractAnthropicDeltaText(evt)
          if (parts.text.length > 0) textBatch += parts.text
          if (parts.thinking.length > 0) thinkingBatch += parts.thinking
        } else if (evt.type === 'message_delta' && 'delta' in evt) {
          stopReason = evt.delta?.stop_reason ?? stopReason
          if ('usage' in evt && typeof evt.usage?.output_tokens === 'number') {
            outputTokens = evt.usage.output_tokens
          }
        }
      }
      if (textBatch.length > 0 || thinkingBatch.length > 0) {
        answerAcc += textBatch
        thinkingAcc += thinkingBatch
        const answerSnap = answerAcc
        const thinkingSnap = thinkingAcc
        startTransition(() => {
          setters.setContent(answerSnap)
          setters.setThinkingContent(thinkingSnap)
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
    hasReasoning: thinkingAcc.length > 0,
  })
  // raw 取最后一个事件 + 累计的关键元数据（流式没有单一 JSON 终响应）
  setters.setRawResponse({
    type: 'anthropic.stream.summary',
    messageId,
    model,
    stopReason,
    usage: { input_tokens: inputTokens, output_tokens: outputTokens },
    text: answerAcc,
    thinkingText: thinkingAcc,
    lastEvent,
  })
  setters.setStatus('done')
}
