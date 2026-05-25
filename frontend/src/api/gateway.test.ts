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
import { GATEWAY_API_BASE } from './paths'

const TEAM_ID = 'team-test'

describe('gatewayApi.listAvailableModels', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('请求 /api/v1/gateway/models/available', async () => {
    mockFetch.mockResolvedValueOnce(
      createMockResponse({
        system_models: {
          items: [],
          total: 0,
          page: 1,
          page_size: 20,
          has_next: false,
          has_prev: false,
        },
        user_models: {
          items: [],
          total: 0,
          page: 1,
          page_size: 20,
          has_next: false,
          has_prev: false,
        },
      })
    )
    await gatewayApi.listAvailableModels('text')
    expect(getLastFetchUrl()).toContain(`${GATEWAY_API_BASE}/models/available`)
    expect(getLastFetchUrl()).toContain('type=text')
  })

  it('不传 type 时无 type query', async () => {
    mockFetch.mockResolvedValueOnce(
      createMockResponse({
        system_models: {
          items: [],
          total: 0,
          page: 1,
          page_size: 20,
          has_next: false,
          has_prev: false,
        },
        user_models: {
          items: [],
          total: 0,
          page: 1,
          page_size: 20,
          has_next: false,
          has_prev: false,
        },
      })
    )
    await gatewayApi.listAvailableModels()
    expect(getLastFetchUrl()).toContain(`${GATEWAY_API_BASE}/models/available`)
    expect(getLastFetchUrl()).not.toContain('type=')
  })

  it('附带 provider 与 mode query', async () => {
    mockFetch.mockResolvedValueOnce(
      createMockResponse({
        system_models: {
          items: [],
          total: 0,
          page: 1,
          page_size: 20,
          has_next: false,
          has_prev: false,
        },
        user_models: {
          items: [],
          total: 0,
          page: 1,
          page_size: 20,
          has_next: false,
          has_prev: false,
        },
      })
    )
    await gatewayApi.listAvailableModels('text', 'volcengine', { mode: 'chat' })
    const url = getLastFetchUrl()
    expect(url).toContain('type=text')
    expect(url).toContain('provider=volcengine')
    expect(url).toContain('mode=chat')
  })

  it('附带 page 与 page_size query', async () => {
    mockFetch.mockResolvedValueOnce(
      createMockResponse({
        system_models: {
          items: [],
          total: 0,
          page: 2,
          page_size: 50,
          has_next: false,
          has_prev: true,
        },
        user_models: {
          items: [],
          total: 0,
          page: 2,
          page_size: 50,
          has_next: false,
          has_prev: true,
        },
      })
    )
    await gatewayApi.listAvailableModels('text', undefined, { page: 2, page_size: 50 })
    const url = getLastFetchUrl()
    expect(url).toContain('page=2')
    expect(url).toContain('page_size=50')
  })
})

describe('gatewayApi.listModels', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('请求团队模型分页 envelope', async () => {
    mockFetch.mockResolvedValueOnce(
      createMockResponse({
        items: [],
        total: 0,
        page: 1,
        page_size: 20,
        has_next: false,
        has_prev: false,
        connectivity_summary: {
          total: 0,
          available: 0,
          unavailable: 0,
          success: 0,
          failed: 0,
          unknown: 0,
        },
      })
    )
    await gatewayApi.listModels(TEAM_ID, {
      page: 1,
      page_size: 20,
      q: 'gpt',
      connectivity: 'failed',
    })
    const url = getLastFetchUrl()
    expect(url).toContain(`${GATEWAY_API_BASE}/teams/${TEAM_ID}/models`)
    expect(url).toContain('page=1')
    expect(url).toContain('page_size=20')
    expect(url).toContain('q=gpt')
    expect(url).toContain('connectivity=failed')
  })
})

describe('gatewayApi.listModelIds', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('请求 /models/ids 并传递筛选 query', async () => {
    mockFetch.mockResolvedValueOnce(createMockResponse({ ids: ['id-1', 'id-2'], truncated: false }))
    const data = await gatewayApi.listModelIds(TEAM_ID, {
      registry_scope: 'requestable',
      connectivity: 'failed',
    })
    const url = getLastFetchUrl()
    expect(url).toContain(`${GATEWAY_API_BASE}/teams/${TEAM_ID}/models/ids`)
    expect(url).toContain('registry_scope=requestable')
    expect(url).toContain('connectivity=failed')
    expect(data.ids).toEqual(['id-1', 'id-2'])
    expect(data.truncated).toBe(false)
  })
})

describe('gatewayApi.listMyModels', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('请求 /my-models 分页 envelope', async () => {
    mockFetch.mockResolvedValueOnce(
      createMockResponse({
        items: [],
        total: 0,
        page: 1,
        page_size: 20,
        has_next: false,
        has_prev: false,
        connectivity_summary: {
          total: 0,
          available: 0,
          unavailable: 0,
          success: 0,
          failed: 0,
          unknown: 0,
        },
      })
    )
    await gatewayApi.listMyModels({ page: 2, page_size: 10, provider: 'openai', q: 'mini' })
    const url = getLastFetchUrl()
    expect(url).toContain(`${GATEWAY_API_BASE}/my-models`)
    expect(url).toContain('page=2')
    expect(url).toContain('page_size=10')
    expect(url).toContain('provider=openai')
    expect(url).toContain('q=mini')
  })
})

describe('gatewayApi.revealKey', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('请求 GET /api/v1/gateway/teams/{teamId}/keys/{id}/reveal', async () => {
    mockFetch.mockResolvedValueOnce(createMockResponse({ plain_key: 'sk-gw-test' }))
    const data = await gatewayApi.revealKey(TEAM_ID, 'key-abc')
    expect(getLastFetchUrl()).toContain(`${GATEWAY_API_BASE}/teams/${TEAM_ID}/keys/key-abc/reveal`)
    expect(data.plain_key).toBe('sk-gw-test')
  })
})

describe('gatewayApi.listVkeyEntitlements', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('请求 GET /api/v1/gateway/teams/{teamId}/keys/{id}/entitlements', async () => {
    mockFetch.mockResolvedValueOnce(createMockResponse([]))
    await gatewayApi.listVkeyEntitlements(TEAM_ID, 'vkey-1')
    expect(getLastFetchUrl()).toContain(
      `${GATEWAY_API_BASE}/teams/${TEAM_ID}/keys/vkey-1/entitlements`
    )
  })
})
