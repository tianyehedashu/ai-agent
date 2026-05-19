/**
 * Playground 视频生成：POST /v1/videos（同步返回，无任务轮询）
 */

import { useCallback } from 'react'

import { parseVideoGenerationResponse } from './media-parse'
import { buildVideoGenRequestBody } from './playground-request'
import { useGatewayPostCall, type UseGatewayPostCallReturn } from './use-gateway-post-call'

import type { PlaygroundMetadata, PlaygroundVideoRawSummary } from './types'

export interface VideoCallParams {
  baseUrl: string
  apiKey: string
  model: string
  prompt: string
  imageUrl?: string
}

export type UsePlaygroundVideoCallReturn = Omit<UseGatewayPostCallReturn, 'send'> & {
  send: (params: VideoCallParams) => Promise<void>
}

export function usePlaygroundVideoCall(): UsePlaygroundVideoCallReturn {
  const base = useGatewayPostCall()

  const send = useCallback(
    async (params: VideoCallParams): Promise<void> => {
      const body = buildVideoGenRequestBody({
        model: params.model,
        prompt: params.prompt,
        imageUrl: params.imageUrl,
      })
      await base.send(
        {
          baseUrl: params.baseUrl,
          apiKey: params.apiKey,
          path: '/videos',
          body,
        },
        (json, httpStatus, elapsedMs, requestId) => {
          const parsed = parseVideoGenerationResponse(json)
          const summary: PlaygroundVideoRawSummary = {
            type: 'video_gen',
            url: parsed.url,
          }
          const metadata: PlaygroundMetadata = { httpStatus, elapsedMs, requestId }
          return {
            content: parsed.summary,
            metadata,
            rawResponse: summary,
          }
        }
      )
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps -- base.send
    [base.send]
  )

  return { ...base, send }
}
