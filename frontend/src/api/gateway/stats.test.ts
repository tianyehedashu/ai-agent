import { describe, expect, it, vi } from 'vitest'

import { statsApi } from './stats'

describe('statsApi usageStats query', () => {
  it('includes filter params in request search', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'Content-Type': 'application/json' }),
      json: () =>
        Promise.resolve({
          items: [],
          total: 0,
          page: 1,
          page_size: 20,
          has_next: false,
          has_prev: false,
          start: '2026-01-01T00:00:00Z',
          end: '2026-01-08T00:00:00Z',
          group_by: 'model',
          totals: {
            requests: 0,
            success_count: 0,
            failure_count: 0,
            input_tokens: 0,
            output_tokens: 0,
            cached_tokens: 0,
            cache_creation_tokens: 0,
            total_tokens: 0,
            cost_usd: 0,
            avg_latency_ms: 0,
            avg_ttfb_ms: 0,
            cache_hit_count: 0,
            success_rate: 0,
            cache_hit_rate: 0,
          },
        }),
      text: () => Promise.resolve(''),
    })
    vi.stubGlobal('fetch', fetchMock)

    await statsApi.usageStats('team-1', {
      usage_aggregation: 'platform',
      start: '2026-01-01T00:00:00.000Z',
      end: '2026-01-31T23:59:59.999Z',
      provider: 'volcengine',
      group_by: 'model',
      page: 1,
      page_size: 20,
    })

    const url = (fetchMock.mock.calls[0] as [string])[0]
    const decodedUrl = decodeURIComponent(url)
    expect(decodedUrl).toContain('usage_aggregation=platform')
    expect(decodedUrl).toContain('start=2026-01-01T00:00:00.000Z')
    expect(decodedUrl).toContain('end=2026-01-31T23:59:59.999Z')
    expect(decodedUrl).toContain('provider=volcengine')
    expect(url).not.toMatch(/[?&]team_id=/)
  })
})
