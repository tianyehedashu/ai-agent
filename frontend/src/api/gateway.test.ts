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
  text: () => Promise<string>
} {
  const json = (): Promise<T> => Promise.resolve(data)
  return {
    ok: true,
    status: 200,
    headers: new Headers({ 'Content-Type': 'application/json' }),
    json,
    text: async (): Promise<string> => JSON.stringify(await json()),
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

describe('gatewayApi.revealKey', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('请求 GET /api/v1/gateway/keys/{id}/reveal', async () => {
    mockFetch.mockResolvedValueOnce(createMockResponse({ plain_key: 'sk-gw-test' }))
    const data = await gatewayApi.revealKey('key-abc')
    expect(getLastFetchUrl()).toContain('/api/v1/gateway/keys/key-abc/reveal')
    expect(data.plain_key).toBe('sk-gw-test')
  })
})

describe('gatewayApi.listVkeyEntitlements', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('请求 GET /api/v1/gateway/keys/{id}/entitlements', async () => {
    mockFetch.mockResolvedValueOnce(createMockResponse([]))
    await gatewayApi.listVkeyEntitlements('vkey-1')
    expect(getLastFetchUrl()).toContain('/api/v1/gateway/keys/vkey-1/entitlements')
  })
})
