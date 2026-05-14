/**
 * User Model API 单测：请求 URL、method 与 body
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

function getLastRequestInit(): RequestInit & { body?: string } {
  const tuple = mockFetch.mock.calls[0] as [string, RequestInit & { body?: string }] | undefined
  if (!tuple) throw new Error('expected fetch to have been called')
  return tuple[1]
}

function getLastFetchUrl(): string {
  const tuple = mockFetch.mock.calls[0] as [string, RequestInit?] | undefined
  if (!tuple) throw new Error('expected fetch to have been called')
  return tuple[0]
}

import type { ModelType } from '@/types/user-model'

import { userModelApi } from './userModel'

describe('userModelApi', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // -----------------------------------------------------------------------
  // create
  // -----------------------------------------------------------------------

  it('create 发送 POST 与完整 body', async () => {
    const body = {
      display_name: 'My GPT',
      provider: 'openai',
      model_id: 'gpt-4o',
      api_key: 'sk-123',
      model_types: ['text', 'image'] as ModelType[],
    }
    mockFetch.mockResolvedValueOnce(createMockResponse({ id: 'uuid-1', ...body, is_system: false }))
    await userModelApi.create(body)
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/user-models'),
      expect.objectContaining({ method: 'POST' })
    )
    const sentBody = JSON.parse(getLastRequestInit().body ?? '{}') as {
      display_name?: string
      provider?: string
      api_key?: string
    }
    expect(sentBody.display_name).toBe('My GPT')
    expect(sentBody.provider).toBe('openai')
    expect(sentBody.api_key).toBe('sk-123')
  })

  // -----------------------------------------------------------------------
  // list
  // -----------------------------------------------------------------------

  it('list 请求正确 URL 与 query 参数', async () => {
    mockFetch.mockResolvedValueOnce(createMockResponse({ items: [], total: 0 }))
    await userModelApi.list({ type: 'text', skip: 0, limit: 20 })
    const url = getLastFetchUrl()
    expect(url).toContain('/api/v1/user-models')
    expect(url).toMatch(/type=text/)
    expect(url).toMatch(/skip=0/)
    expect(url).toMatch(/limit=20/)
  })

  it('list 附带 provider query', async () => {
    mockFetch.mockResolvedValueOnce(createMockResponse({ items: [], total: 0 }))
    await userModelApi.list({ provider: 'deepseek', limit: 50 })
    const url = getLastFetchUrl()
    expect(url).toMatch(/provider=deepseek/)
  })

  it('list 不传参数时不附带 query', async () => {
    mockFetch.mockResolvedValueOnce(createMockResponse({ items: [], total: 0 }))
    await userModelApi.list()
    const url = getLastFetchUrl()
    expect(url).not.toMatch(/type=/)
    expect(url).not.toMatch(/skip=/)
  })

  // -----------------------------------------------------------------------
  // listAvailable
  // -----------------------------------------------------------------------

  it('listAvailable 请求 /available', async () => {
    mockFetch.mockResolvedValueOnce(createMockResponse({ system_models: [], user_models: [] }))
    await userModelApi.listAvailable('text')
    const url = getLastFetchUrl()
    expect(url).toContain('/api/v1/user-models/available')
    expect(url).toMatch(/type=text/)
  })

  it('listAvailable 不传 type 时无 query', async () => {
    mockFetch.mockResolvedValueOnce(createMockResponse({ system_models: [], user_models: [] }))
    await userModelApi.listAvailable()
    const url = getLastFetchUrl()
    expect(url).not.toMatch(/type=/)
  })

  it('listAvailable 附带 provider query', async () => {
    mockFetch.mockResolvedValueOnce(createMockResponse({ system_models: [], user_models: [] }))
    await userModelApi.listAvailable('text', 'volcengine')
    const url = getLastFetchUrl()
    expect(url).toMatch(/type=text/)
    expect(url).toMatch(/provider=volcengine/)
  })

  // -----------------------------------------------------------------------
  // get
  // -----------------------------------------------------------------------

  it('get 请求正确 URL', async () => {
    mockFetch.mockResolvedValueOnce(createMockResponse({ id: 'uuid-1', display_name: 'M' }))
    await userModelApi.get('uuid-1')
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringMatching(/\/api\/v1\/user-models\/uuid-1$/),
      expect.any(Object)
    )
  })

  // -----------------------------------------------------------------------
  // update
  // -----------------------------------------------------------------------

  it('update 发送 PATCH 与部分字段', async () => {
    mockFetch.mockResolvedValueOnce(createMockResponse({ id: 'uuid-1', display_name: 'New' }))
    await userModelApi.update('uuid-1', { display_name: 'New' })
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/user-models/uuid-1'),
      expect.objectContaining({ method: 'PATCH' })
    )
    const sentBody = JSON.parse(getLastRequestInit().body ?? '{}') as {
      display_name?: string
      provider?: string
      api_key?: string
    }
    expect(sentBody.display_name).toBe('New')
  })

  // -----------------------------------------------------------------------
  // delete
  // -----------------------------------------------------------------------

  it('delete 发送 DELETE', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 204,
      headers: new Headers(),
      json: () => Promise.resolve(null),
      text: () => Promise.resolve(''),
    })
    await userModelApi.delete('uuid-1')
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/user-models/uuid-1'),
      expect.objectContaining({ method: 'DELETE' })
    )
  })

  // -----------------------------------------------------------------------
  // testConnection
  // -----------------------------------------------------------------------

  it('testConnection 发送 POST 到 /{id}/test', async () => {
    mockFetch.mockResolvedValueOnce(
      createMockResponse({ success: true, message: '连接成功', model: 'gpt-4o' })
    )
    const result = await userModelApi.testConnection('uuid-1')
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/user-models/uuid-1/test'),
      expect.objectContaining({ method: 'POST' })
    )
    expect(result.success).toBe(true)
  })
})
