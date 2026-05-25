import { describe, expect, it } from 'vitest'

import {
  GATEWAY_HEADER_PREFLIGHT_MS,
  GATEWAY_HEADER_UPSTREAM_MS,
  mergePlaygroundTimingFields,
  parseGatewayTimingHeaders,
} from './playground-timing'

describe('parseGatewayTimingHeaders', () => {
  it('reads preflight and upstream headers', () => {
    const headers = new Headers({
      [GATEWAY_HEADER_PREFLIGHT_MS]: '120',
      [GATEWAY_HEADER_UPSTREAM_MS]: '7100',
    })
    expect(parseGatewayTimingHeaders(headers)).toEqual({
      preflightMs: 120,
      upstreamMs: 7100,
    })
  })

  it('returns undefined for missing headers', () => {
    expect(parseGatewayTimingHeaders(new Headers())).toEqual({})
  })
})

describe('mergePlaygroundTimingFields', () => {
  it('keeps upstream from header when present', () => {
    expect(mergePlaygroundTimingFields(7450, { preflightMs: 120, upstreamMs: 7100 }, 820)).toEqual({
      preflightMs: 120,
      upstreamMs: 7100,
      ttftMs: 820,
    })
  })

  it('estimates upstream from elapsed minus preflight for stream MVP', () => {
    expect(mergePlaygroundTimingFields(7450, { preflightMs: 120 }, 820)).toEqual({
      preflightMs: 120,
      upstreamMs: 7330,
      ttftMs: 820,
    })
  })

  it('omits ttftMs for non-stream responses', () => {
    expect(mergePlaygroundTimingFields(7450, { preflightMs: 120, upstreamMs: 7100 })).toEqual({
      preflightMs: 120,
      upstreamMs: 7100,
    })
  })
})
