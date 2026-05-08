/**
 * Product Info API 单测：请求 URL 与 body
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

// 在 mock fetch 后导入，以便 apiClient 使用 mock
import { productInfoApi } from './productInfo'

describe('productInfoApi', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('listJobs 请求正确 URL 与参数', async () => {
    mockFetch.mockResolvedValueOnce(createMockResponse({ items: [], total: 0, skip: 0, limit: 20 }))
    await productInfoApi.listJobs({ skip: 0, limit: 20, status: 'draft' })
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/product-info/jobs'),
      expect.any(Object)
    )
    expect(getLastFetchUrl()).toMatch(/skip=0&limit=20&status=draft/)
  })

  it('getJob 请求正确 URL', async () => {
    mockFetch.mockResolvedValueOnce(
      createMockResponse({ id: 'job-1', status: 'completed', steps: [] })
    )
    await productInfoApi.getJob('job-1')
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringMatching(/\/api\/v1\/product-info\/jobs\/job-1$/),
      expect.any(Object)
    )
  })

  it('runStep 发送 POST 与 body', async () => {
    mockFetch.mockResolvedValueOnce(
      createMockResponse({ id: 'job-1', status: 'running', steps: [] })
    )
    await productInfoApi.runStep('job-1', {
      capability_id: 'image_analysis',
      user_input: { product_link: 'https://a.com' },
    })
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/product-info/jobs/job-1/steps'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          capability_id: 'image_analysis',
          user_input: { product_link: 'https://a.com' },
        }),
      })
    )
  })

  it('runStep 传递 phase=generate_prompt 与 meta_prompt', async () => {
    mockFetch.mockResolvedValueOnce(
      createMockResponse({ id: 'job-1', status: 'running', steps: [] })
    )
    await productInfoApi.runStep('job-1', {
      capability_id: 'product_link_analysis',
      user_input: { product_link: 'https://a.com' },
      phase: 'generate_prompt',
      meta_prompt: 'Analyze carefully',
    })
    const body = JSON.parse(getLastRequestInit().body ?? '{}') as {
      phase?: string
      meta_prompt?: string
      generated_prompt?: string
      capability_id?: string
      user_input?: unknown
    }
    expect(body.phase).toBe('generate_prompt')
    expect(body.meta_prompt).toBe('Analyze carefully')
    expect(body.generated_prompt).toBeUndefined()
  })

  it('runStep 传递 phase=execute 与 generated_prompt', async () => {
    mockFetch.mockResolvedValueOnce(
      createMockResponse({ id: 'job-1', status: 'running', steps: [] })
    )
    await productInfoApi.runStep('job-1', {
      capability_id: 'product_link_analysis',
      user_input: {},
      phase: 'execute',
      generated_prompt: 'User edited prompt',
    })
    const body = JSON.parse(getLastRequestInit().body ?? '{}') as {
      phase?: string
      meta_prompt?: string
      generated_prompt?: string
      capability_id?: string
      user_input?: unknown
    }
    expect(body.phase).toBe('execute')
    expect(body.generated_prompt).toBe('User edited prompt')
  })

  it('runStep 传递 phase=full 与 meta_prompt', async () => {
    mockFetch.mockResolvedValueOnce(
      createMockResponse({ id: 'job-1', status: 'running', steps: [] })
    )
    await productInfoApi.runStep('job-1', {
      capability_id: 'image_analysis',
      user_input: {},
      phase: 'full',
      meta_prompt: 'Full meta',
    })
    const body = JSON.parse(getLastRequestInit().body ?? '{}') as {
      phase?: string
      meta_prompt?: string
      generated_prompt?: string
      capability_id?: string
      user_input?: unknown
    }
    expect(body.phase).toBe('full')
    expect(body.meta_prompt).toBe('Full meta')
  })

  it('runStep 不传 phase 时默认不含该字段', async () => {
    mockFetch.mockResolvedValueOnce(
      createMockResponse({ id: 'job-1', status: 'running', steps: [] })
    )
    await productInfoApi.runStep('job-1', {
      capability_id: 'image_analysis',
      user_input: { product_name: 'A' },
    })
    const body = JSON.parse(getLastRequestInit().body ?? '{}') as {
      phase?: string
      meta_prompt?: string
      generated_prompt?: string
      capability_id?: string
      user_input?: unknown
    }
    expect(body.capability_id).toBe('image_analysis')
    expect(body.user_input).toEqual({ product_name: 'A' })
  })

  it('run 一键执行发送 POST 与 body', async () => {
    mockFetch.mockResolvedValueOnce(
      createMockResponse({ job_id: 'job-1', status: 'running', message: '', poll_url: '' })
    )
    await productInfoApi.run({ inputs: { product_name: '商品' } })
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/product-info/run'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ inputs: { product_name: '商品' } }),
      })
    )
  })
})
