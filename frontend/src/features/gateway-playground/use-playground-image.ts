/**
 * Playground 图片生成：POST /v1/images/generations
 */

import { useCallback } from 'react'

import { imageItemsToDisplayContent, parseImageGenerationResponse } from './media-parse'
import { buildImageGenRequestBody } from './playground-request'
import { useGatewayPostCall, type UseGatewayPostCallReturn } from './use-gateway-post-call'

import type { PlaygroundImageRawSummary, PlaygroundMetadata } from './types'

export interface ImageCallParams {
  baseUrl: string
  apiKey: string
  model: string
  prompt: string
  size?: string
  n?: number
}

export type UsePlaygroundImageCallReturn = Omit<UseGatewayPostCallReturn, 'send'> & {
  send: (params: ImageCallParams) => Promise<void>
}

export function usePlaygroundImageCall(): UsePlaygroundImageCallReturn {
  const base = useGatewayPostCall()

  const send = useCallback(
    async (params: ImageCallParams): Promise<void> => {
      const body = buildImageGenRequestBody({
        model: params.model,
        prompt: params.prompt,
        size: params.size,
        n: params.n ?? 1,
        responseFormat: 'url',
      })
      await base.send(
        {
          baseUrl: params.baseUrl,
          apiKey: params.apiKey,
          path: '/images/generations',
          body,
        },
        (json, httpStatus, elapsedMs, requestId) => {
          const items = parseImageGenerationResponse(json)
          const summary: PlaygroundImageRawSummary = { type: 'image_gen', items }
          const metadata: PlaygroundMetadata = { httpStatus, elapsedMs, requestId }
          return {
            content: imageItemsToDisplayContent(items),
            metadata,
            rawResponse: summary,
          }
        }
      )
    },
    // base 经 useMemo 稳定；仅需 send
    // eslint-disable-next-line react-hooks/exhaustive-deps -- base.send
    [base.send]
  )

  return { ...base, send }
}
