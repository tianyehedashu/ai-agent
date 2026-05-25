/**
 * 解析 OpenAI 兼容面试调诊断响应头（见 docs/API_RESPONSE.md §5）
 */

import type { PlaygroundMetadata } from './types'

export const GATEWAY_HEADER_PREFLIGHT_MS = 'x-gateway-preflight-ms'
export const GATEWAY_HEADER_UPSTREAM_MS = 'x-gateway-upstream-ms'

export interface GatewayTimingFromHeaders {
  preflightMs?: number
  upstreamMs?: number
}

function parseTimingHeaderMs(raw: string | null): number | undefined {
  if (raw === null || raw.trim() === '') return undefined
  const parsed = Number.parseInt(raw, 10)
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : undefined
}

export function parseGatewayTimingHeaders(headers: Headers): GatewayTimingFromHeaders {
  return {
    preflightMs: parseTimingHeaderMs(headers.get(GATEWAY_HEADER_PREFLIGHT_MS)),
    upstreamMs: parseTimingHeaderMs(headers.get(GATEWAY_HEADER_UPSTREAM_MS)),
  }
}

/** 合并响应头耗时与端到端 elapsed；流式无上游头时用总耗时减预检估算。 */
export function mergePlaygroundTimingFields(
  elapsedMs: number,
  headers: GatewayTimingFromHeaders,
  ttftMs?: number
): Pick<PlaygroundMetadata, 'preflightMs' | 'upstreamMs' | 'ttftMs'> {
  const preflightMs = headers.preflightMs
  let upstreamMs = headers.upstreamMs
  if (upstreamMs === undefined && preflightMs !== undefined && elapsedMs >= preflightMs) {
    upstreamMs = elapsedMs - preflightMs
  }
  return {
    preflightMs,
    upstreamMs,
    ...(ttftMs !== undefined ? { ttftMs } : {}),
  }
}
