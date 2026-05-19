/**
 * Playground 通用 POST 调用（非流式 JSON）：图片/视频生成等共享 abort、metadata、错误解析。
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import {
  buildNetworkPlaygroundError,
  extractPlaygroundHttpError,
  readPlaygroundErrorBody,
} from './playground-error'
import { maskAuthHeadersForDisplay } from './playground-request'

import type {
  PlaygroundError,
  PlaygroundMetadata,
  PlaygroundRawResponse,
  PlaygroundRequestSnapshot,
  PlaygroundStatus,
} from './types'

export interface GatewayPostExecuteParams {
  baseUrl: string
  apiKey: string
  path: string
  body: Record<string, unknown>
}

export interface GatewayPostParseResult {
  content: string
  metadata: PlaygroundMetadata
  rawResponse: PlaygroundRawResponse
}

export interface UseGatewayPostCallReturn {
  status: PlaygroundStatus
  content: string
  metadata: PlaygroundMetadata | null
  error: PlaygroundError | null
  rawResponse: PlaygroundRawResponse
  lastRequest: PlaygroundRequestSnapshot | null
  isRunning: boolean
  send: (
    params: GatewayPostExecuteParams,
    parse: (
      json: unknown,
      httpStatus: number,
      elapsedMs: number,
      requestId?: string
    ) => GatewayPostParseResult
  ) => Promise<void>
  cancel: () => void
  reset: () => void
}

export function useGatewayPostCall(): UseGatewayPostCallReturn {
  const [status, setStatus] = useState<PlaygroundStatus>('idle')
  const [content, setContent] = useState('')
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
    setMetadata(null)
    setError(null)
    setRawResponse(null)
    setLastRequest(null)
  }, [])

  const cancel = useCallback(() => {
    abortRef.current?.abort()
  }, [])

  const send = useCallback(
    async (
      params: GatewayPostExecuteParams,
      parse: (
        json: unknown,
        httpStatus: number,
        elapsedMs: number,
        requestId?: string
      ) => GatewayPostParseResult
    ): Promise<void> => {
      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller
      setStatus('pending')
      setContent('')
      setMetadata(null)
      setError(null)
      setRawResponse(null)
      setLastRequest(null)

      const startedAt = performance.now()
      const baseTrimmed = params.baseUrl.replace(/\/$/, '')
      const url = `${baseTrimmed}${params.path.startsWith('/') ? params.path : `/${params.path}`}`
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${params.apiKey}`,
      }

      setLastRequest({
        method: 'POST',
        url,
        headers: maskAuthHeadersForDisplay(headers),
        body: params.body,
      })

      let response: Response
      try {
        response = await fetch(url, {
          method: 'POST',
          headers,
          body: JSON.stringify(params.body),
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
      const elapsedMs = Math.round(performance.now() - startedAt)

      if (!response.ok) {
        const errorJson = await readPlaygroundErrorBody(response)
        const fallback = `HTTP ${String(response.status)} ${response.statusText}`
        setStatus('error')
        setError(extractPlaygroundHttpError(errorJson, response.status, fallback, 'openai'))
        setMetadata({ httpStatus: response.status, elapsedMs, requestId })
        setRawResponse(errorJson)
        return
      }

      let json: unknown = null
      try {
        json = await response.json()
      } catch (e) {
        setStatus('error')
        setError({
          httpStatus: response.status,
          message: e instanceof Error ? e.message : '响应解析失败',
        })
        return
      }

      const parsed = parse(json, response.status, elapsedMs, requestId)
      setContent(parsed.content)
      setMetadata(parsed.metadata)
      setRawResponse(parsed.rawResponse)
      setStatus('done')
    },
    []
  )

  return useMemo(
    () => ({
      status,
      content,
      metadata,
      error,
      rawResponse,
      lastRequest,
      isRunning: status === 'pending',
      send,
      cancel,
      reset,
    }),
    [status, content, metadata, error, rawResponse, lastRequest, send, cancel, reset]
  )
}
