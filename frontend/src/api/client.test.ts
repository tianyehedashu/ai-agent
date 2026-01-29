/**
 * API Client 单元测试
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// Mock localStorage
const localStorageMock = {
  getItem: vi.fn(),
  setItem: vi.fn(),
  removeItem: vi.fn(),
}
Object.defineProperty(globalThis, 'localStorage', { value: localStorageMock })

// Mock fetch
const mockFetch = vi.fn()
globalThis.fetch = mockFetch

// 重新导入以使用 mock
import { apiClient } from './client'

describe('ApiClient', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorageMock.getItem.mockReturnValue(null)
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('buildUrl', () => {
    it('应该正确构建相对路径（开发环境，无 baseUrl）', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ data: 'test' }),
      })

      await apiClient.get('/api/v1/test')

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/v1/test',
        expect.objectContaining({
          method: 'GET',
        })
      )
    })

    it('应该正确处理查询参数', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ data: 'test' }),
      })

      await apiClient.get('/api/v1/test', { skip: 0, limit: 10 })

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/v1/test?skip=0&limit=10',
        expect.objectContaining({
          method: 'GET',
        })
      )
    })

    it('应该忽略 undefined 的查询参数', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ data: 'test' }),
      })

      await apiClient.get('/api/v1/test', { skip: 0, limit: undefined })

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/v1/test?skip=0',
        expect.objectContaining({
          method: 'GET',
        })
      )
    })
  })

  describe('HTTP Methods', () => {
    it('GET 请求应该正常工作', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ id: 1 }),
      })

      const result = await apiClient.get('/api/v1/users/1')

      expect(result).toEqual({ id: 1 })
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/v1/users/1',
        expect.objectContaining({
          method: 'GET',
          headers: expect.objectContaining({
            'Content-Type': 'application/json',
          }) as Record<string, unknown>,
        }) as RequestInit
      )
    })

    it('请求应该携带 credentials: include 以支持 Cookie', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ data: 'test' }),
      })

      await apiClient.get('/api/v1/test')

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/v1/test',
        expect.objectContaining({
          credentials: 'include',
        })
      )
    })

    it('POST 请求应该正常工作', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ id: 1, name: 'test' }),
      })

      const result = await apiClient.post('/api/v1/users', { name: 'test' })

      expect(result).toEqual({ id: 1, name: 'test' })
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/v1/users',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ name: 'test' }),
        })
      )
    })

    it('PUT 请求应该正常工作', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ id: 1, name: 'updated' }),
      })

      const result = await apiClient.put('/api/v1/users/1', { name: 'updated' })

      expect(result).toEqual({ id: 1, name: 'updated' })
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/v1/users/1',
        expect.objectContaining({
          method: 'PUT',
          body: JSON.stringify({ name: 'updated' }),
        })
      )
    })

    it('DELETE 请求应该正常工作', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ success: true }),
      })

      const result = await apiClient.delete('/api/v1/users/1')

      expect(result).toEqual({ success: true })
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/v1/users/1',
        expect.objectContaining({
          method: 'DELETE',
        })
      )
    })
  })

  describe('错误处理', () => {
    it('应该正确处理 HTTP 错误', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
        json: () => Promise.resolve({ detail: 'Not found' }),
      })

      await expect(apiClient.get('/api/v1/notfound')).rejects.toThrow('Not found')
    })

    it('应该处理无 detail 的错误响应', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: () => Promise.resolve({ message: 'Server error' }),
      })

      await expect(apiClient.get('/api/v1/error')).rejects.toThrow('Server error')
    })

    it('应该处理无法解析的错误响应', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: () => Promise.reject(new Error('Invalid JSON')),
      })

      // 当 JSON 解析失败时，fallback 到 'Unknown error'
      await expect(apiClient.get('/api/v1/error')).rejects.toThrow('Unknown error')
    })
  })

  describe('Token 管理', () => {
    it('应该在请求头中包含 token', async () => {
      // 设置 token
      apiClient.setToken('test-token')

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ data: 'test' }),
      })

      await apiClient.get('/api/v1/protected')

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/v1/protected',
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: 'Bearer test-token',
          }) as Record<string, unknown>,
        }) as RequestInit
      )
    })

    it('setToken 应该保存到 localStorage', () => {
      apiClient.setToken('new-token')

      expect(localStorageMock.setItem).toHaveBeenCalledWith('auth_token', 'new-token')
    })

    it('setToken(null) 应该从 localStorage 移除', () => {
      apiClient.setToken(null)

      expect(localStorageMock.removeItem).toHaveBeenCalledWith('auth_token')
    })
  })
})
