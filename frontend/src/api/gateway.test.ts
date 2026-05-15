/**
 * Gateway API 单测：listAvailableModels 请求 URL 与 query
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockFetch = vi.fn()
globalThis.fetch = mockFetch

function createMockResponse<T>(data: T): {
  ok: boolean
  status: number
  headers: Headers
  json: () => Promise<T>
} {
  return {
    ok: true,
    status: 200,
    headers: new Headers({ 'Content-Type': 'application/json' }),
    json: () => Promise.resolve(data),
  }
}

function getLastFetchUrl(): string {
  const tuple = mockFetch.mock.calls[0] as [string, RequestInit?] | undefined
  if (!tuple) throw new Error('expected fetch to have been called')
  return tuple[0]
}

import { gatewayApi } from './gateway'

describe('gatewayApi.listAvailableModels', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('请求 /api/v1/gateway/models/available', async () => {
    mockFetch.mockResolvedValueOnce(createMockResponse({ system_models: [], user_models: [] }))
    await gatewayApi.listAvailableModels('text')
    expect(getLastFetchUrl()).toContain('/api/v1/gateway/models/available')
    expect(getLastFetchUrl()).toContain('type=text')
  })

  it('不传 type 时无 type query', async () => {
    mockFetch.mockResolvedValueOnce(createMockResponse({ system_models: [], user_models: [] }))
    await gatewayApi.listAvailableModels()
    expect(getLastFetchUrl()).toContain('/api/v1/gateway/models/available')
    expect(getLastFetchUrl()).not.toContain('type=')
  })

  it('附带 provider 与 mode query', async () => {
    mockFetch.mockResolvedValueOnce(createMockResponse({ system_models: [], user_models: [] }))
    await gatewayApi.listAvailableModels('text', 'volcengine', { mode: 'chat' })
    const url = getLastFetchUrl()
    expect(url).toContain('type=text')
    expect(url).toContain('provider=volcengine')
    expect(url).toContain('mode=chat')
  })
})
