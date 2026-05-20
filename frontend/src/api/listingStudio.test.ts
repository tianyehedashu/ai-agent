/**
 * Listing Studio API 单测：请求 URL 与 body
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
  return {
    ok: true,
    status: 200,
    headers: new Headers({ 'Content-Type': 'application/json' }),
    json: () => Promise.resolve(data),
    text: () => Promise.resolve(JSON.stringify(data)),
  }
}

function getLastFetchUrl(): string {
  const tuple = mockFetch.mock.calls[0] as [string, RequestInit?] | undefined
  if (!tuple) throw new Error('expected fetch to have been called')
  return tuple[0]
}

import { listingStudioApi } from './listingStudio'

describe('listingStudioApi', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('listJobs 请求正确 URL 与参数', async () => {
    mockFetch.mockResolvedValueOnce(createMockResponse({ items: [], total: 0, skip: 0, limit: 20 }))
    await listingStudioApi.listJobs({ skip: 0, limit: 20, status: 'draft' })
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/listing-studio/jobs'),
      expect.any(Object)
    )
    expect(getLastFetchUrl()).toMatch(/skip=0&limit=20&status=draft/)
  })

  it('getJob 请求正确 URL', async () => {
    mockFetch.mockResolvedValueOnce(
      createMockResponse({ id: 'job-1', status: 'completed', steps: [] })
    )
    await listingStudioApi.getJob('job-1')
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringMatching(/\/api\/v1\/listing-studio\/jobs\/job-1$/),
      expect.any(Object)
    )
  })

  it('runStep 发送 POST 与 body', async () => {
    mockFetch.mockResolvedValueOnce(
      createMockResponse({ id: 'job-1', status: 'running', steps: [] })
    )
    await listingStudioApi.runStep('job-1', {
      capability_id: 'image_analysis',
      user_input: { product_link: 'https://a.com' },
    })
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/listing-studio/jobs/job-1/steps'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          capability_id: 'image_analysis',
          user_input: { product_link: 'https://a.com' },
        }),
      })
    )
  })

  it('run 一键执行发送 POST 与 body', async () => {
    mockFetch.mockResolvedValueOnce(
      createMockResponse({ job_id: 'job-1', status: 'running', message: '', poll_url: '' })
    )
    await listingStudioApi.run({ inputs: { product_name: '商品' } })
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/listing-studio/run'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ inputs: { product_name: '商品' } }),
      })
    )
  })
})
