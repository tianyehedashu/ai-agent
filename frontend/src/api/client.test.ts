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

/** 创建符合 client.request 要求的 Response 形状（含 headers.get） */
function createMockResponse(overrides: {
  ok?: boolean
  status?: number
  json: () => Promise<unknown>
}): {
  ok: boolean
  status: number
  headers: { get: (_name: string) => string | null }
  json: () => Promise<unknown>
} {
  return {
    ok: true,
    status: 200,
    headers: {
      get: (_name: string) => null as string | null,
    },
    ...overrides,
  }
}

// 重新导入以使用 mock
import { getAuthToken } from '@/stores/auth'

import { apiClient, ApiError } from './client'

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
      mockFetch.mockResolvedValueOnce(
        createMockResponse({ ok: true, json: () => Promise.resolve({ data: 'test' }) })
      )

      await apiClient.get('/api/v1/test')

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/v1/test',
        expect.objectContaining({
          method: 'GET',
        })
      )
    })

    it('应该正确处理查询参数', async () => {
      mockFetch.mockResolvedValueOnce(
        createMockResponse({ ok: true, json: () => Promise.resolve({ data: 'test' }) })
      )

      await apiClient.get('/api/v1/test', { skip: 0, limit: 10 })

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/v1/test?skip=0&limit=10',
        expect.objectContaining({
          method: 'GET',
        })
      )
    })

    it('应该忽略 undefined 的查询参数', async () => {
      mockFetch.mockResolvedValueOnce(
        createMockResponse({ ok: true, json: () => Promise.resolve({ data: 'test' }) })
      )

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
      mockFetch.mockResolvedValueOnce(
        createMockResponse({ ok: true, json: () => Promise.resolve({ id: 1 }) })
      )

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
      mockFetch.mockResolvedValueOnce(
        createMockResponse({ ok: true, json: () => Promise.resolve({ data: 'test' }) })
      )

      await apiClient.get('/api/v1/test')

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/v1/test',
        expect.objectContaining({
          credentials: 'include',
        })
      )
    })

    it('POST 请求应该正常工作', async () => {
      mockFetch.mockResolvedValueOnce(
        createMockResponse({
          ok: true,
          json: () => Promise.resolve({ id: 1, name: 'test' }),
        })
      )

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
      mockFetch.mockResolvedValueOnce(
        createMockResponse({
          ok: true,
          json: () => Promise.resolve({ id: 1, name: 'updated' }),
        })
      )

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
      mockFetch.mockResolvedValueOnce(
        createMockResponse({
          ok: true,
          json: () => Promise.resolve({ success: true }),
        })
      )

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
    it('应该抛出 ApiError 并携带 HTTP 状态码', async () => {
      mockFetch.mockResolvedValueOnce(
        createMockResponse({
          ok: false,
          status: 404,
          json: () => Promise.resolve({ detail: 'Not found' }),
        })
      )

      try {
        await apiClient.get('/api/v1/notfound')
        expect.fail('Should have thrown')
      } catch (error) {
        expect(error).toBeInstanceOf(ApiError)
        expect((error as ApiError).status).toBe(404)
        expect((error as ApiError).message).toBe('Not found')
      }
    })

    it('应该处理无 detail 的错误响应', async () => {
      mockFetch.mockResolvedValueOnce(
        createMockResponse({
          ok: false,
          status: 500,
          json: () => Promise.resolve({ message: 'Server error' }),
        })
      )

      await expect(apiClient.get('/api/v1/error')).rejects.toThrow('Server error')
    })

    it('应该处理无法解析的错误响应', async () => {
      mockFetch.mockResolvedValueOnce(
        createMockResponse({
          ok: false,
          status: 500,
          json: () => Promise.reject(new Error('Invalid JSON')),
        })
      )

      await expect(apiClient.get('/api/v1/error')).rejects.toThrow('Unknown error')
    })
  })

  describe('Token 降级检测', () => {
    it('应该在收到 X-Token-Degraded 响应头时清除过期 token 并派发事件', async () => {
      // Arrange: 设置一个 token（模拟已登录状态）
      apiClient.setToken('expired-token')
      const dispatchSpy = vi.spyOn(window, 'dispatchEvent')

      mockFetch.mockResolvedValueOnce(
        createMockResponse({
          ok: true,
          json: () => Promise.resolve({ id: 'anon', is_anonymous: true }),
          headers: {
            get: (name: string) =>
              name === 'X-Token-Degraded' ? 'true' : null,
          },
        } as Parameters<typeof createMockResponse>[0])
      )

      // Act
      await apiClient.get('/api/v1/auth/me')

      // Assert: token 应该被清除 + 事件应该被派发
      expect(getAuthToken()).toBeNull()
      expect(dispatchSpy).toHaveBeenCalledWith(
        expect.objectContaining({ type: 'auth:token-degraded' })
      )
      dispatchSpy.mockRestore()
    })

    it('没有 X-Token-Degraded 响应头时不应清除 token', async () => {
      // Arrange: 设置有效 token
      apiClient.setToken('valid-token')

      mockFetch.mockResolvedValueOnce(
        createMockResponse({
          ok: true,
          json: () => Promise.resolve({ id: '123', is_anonymous: false }),
        })
      )

      // Act
      await apiClient.get('/api/v1/auth/me')

      // Assert: token 应该保持不变
      expect(getAuthToken()).toBe('valid-token')
    })

    it('没有本地 token 时不应受 X-Token-Degraded 影响', async () => {
      // Arrange: 确保没有 token
      apiClient.setToken(null)

      mockFetch.mockResolvedValueOnce(
        createMockResponse({
          ok: true,
          json: () => Promise.resolve({ id: 'anon', is_anonymous: true }),
          headers: {
            get: (name: string) =>
              name === 'X-Token-Degraded' ? 'true' : null,
          },
        } as Parameters<typeof createMockResponse>[0])
      )

      // Act
      await apiClient.get('/api/v1/test')

      // Assert: 无 token 时不会触发清除逻辑
      expect(getAuthToken()).toBeNull()
    })
  })

  describe('Token 管理', () => {
    it('应该在请求头中包含 token', async () => {
      // 设置 token
      apiClient.setToken('test-token')

      mockFetch.mockResolvedValueOnce(
        createMockResponse({ ok: true, json: () => Promise.resolve({ data: 'test' }) })
      )

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

    it('setToken 应该更新 authStore 状态', () => {
      apiClient.setToken('new-token')

      expect(getAuthToken()).toBe('new-token')
    })

    it('setToken(null) 应该清除 authStore 中的 token', () => {
      apiClient.setToken('new-token')
      expect(getAuthToken()).toBe('new-token')

      apiClient.setToken(null)
      expect(getAuthToken()).toBeNull()
    })
  })
})
