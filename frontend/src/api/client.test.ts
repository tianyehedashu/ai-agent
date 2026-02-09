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
import { getAuthToken, getRefreshToken, setRefreshToken } from '@/stores/auth'

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

  describe('Token 过期与自动续期', () => {
    afterEach(() => {
      apiClient.setToken(null)
      setRefreshToken(null)
    })

    it('401 + 有 refresh_token 时应自动续期并重试请求', async () => {
      // Arrange: 设置过期 access_token 和有效 refresh_token
      apiClient.setToken('expired-token')
      setRefreshToken('valid-refresh-token')
      const dispatchSpy = vi.spyOn(window, 'dispatchEvent')

      // 第1次 fetch: 原始请求 → 401
      mockFetch.mockResolvedValueOnce(
        createMockResponse({
          ok: false,
          status: 401,
          json: () => Promise.resolve({ detail: 'Token expired' }),
        })
      )
      // 第2次 fetch: refresh 请求 → 200 + 新 token pair
      mockFetch.mockResolvedValueOnce(
        createMockResponse({
          ok: true,
          json: () =>
            Promise.resolve({
              access_token: 'new-access-token',
              refresh_token: 'new-refresh-token',
            }),
        })
      )
      // 第3次 fetch: 重试原始请求 → 200
      mockFetch.mockResolvedValueOnce(
        createMockResponse({
          ok: true,
          json: () => Promise.resolve({ id: '123', name: 'Leo' }),
        })
      )

      // Act
      const result = await apiClient.get('/api/v1/auth/me')

      // Assert: 请求成功，token 已更新，无 session-expired 事件
      expect(result).toEqual({ id: '123', name: 'Leo' })
      expect(getAuthToken()).toBe('new-access-token')
      expect(getRefreshToken()).toBe('new-refresh-token')
      expect(dispatchSpy).not.toHaveBeenCalledWith(
        expect.objectContaining({ type: 'auth:session-expired' })
      )
      dispatchSpy.mockRestore()
    })

    it('401 + refresh 也失败时应派发 session-expired 事件', async () => {
      // Arrange
      apiClient.setToken('expired-token')
      setRefreshToken('expired-refresh-token')
      const dispatchSpy = vi.spyOn(window, 'dispatchEvent')

      // 第1次 fetch: 原始请求 → 401
      mockFetch.mockResolvedValueOnce(
        createMockResponse({
          ok: false,
          status: 401,
          json: () => Promise.resolve({ detail: 'Token expired' }),
        })
      )
      // 第2次 fetch: refresh 请求 → 401（refresh token 也过期）
      mockFetch.mockResolvedValueOnce(
        createMockResponse({
          ok: false,
          status: 401,
          json: () => Promise.resolve({ detail: 'Invalid refresh token' }),
        })
      )

      // Act
      await expect(apiClient.get('/api/v1/auth/me')).rejects.toThrow(ApiError)

      // Assert: token 被清除 + 派发 session-expired
      expect(getAuthToken()).toBeNull()
      expect(dispatchSpy).toHaveBeenCalledWith(
        expect.objectContaining({ type: 'auth:session-expired' })
      )
      dispatchSpy.mockRestore()
    })

    it('401 + 无 refresh_token 时应直接派发 session-expired 事件', async () => {
      // Arrange: 有 access_token 但无 refresh_token
      apiClient.setToken('expired-token')
      setRefreshToken(null)
      const dispatchSpy = vi.spyOn(window, 'dispatchEvent')

      mockFetch.mockResolvedValueOnce(
        createMockResponse({
          ok: false,
          status: 401,
          json: () => Promise.resolve({ detail: 'Token expired' }),
        })
      )

      // Act
      await expect(apiClient.get('/api/v1/auth/me')).rejects.toThrow(ApiError)

      // Assert: 无 refresh_token 可用，直接提示过期
      expect(dispatchSpy).toHaveBeenCalledWith(
        expect.objectContaining({ type: 'auth:session-expired' })
      )
      dispatchSpy.mockRestore()
    })

    it('401 + 无 token 时不应尝试 refresh 也不应派发 session-expired', async () => {
      // Arrange: 匿名用户，无 token
      apiClient.setToken(null)
      setRefreshToken(null)
      const dispatchSpy = vi.spyOn(window, 'dispatchEvent')

      mockFetch.mockResolvedValueOnce(
        createMockResponse({
          ok: false,
          status: 401,
          json: () => Promise.resolve({ detail: 'Authentication required' }),
        })
      )

      // Act
      await expect(apiClient.get('/api/v1/protected')).rejects.toThrow(ApiError)

      // Assert: 不应有 refresh 调用或 session-expired 事件
      expect(mockFetch).toHaveBeenCalledTimes(1) // 只有原始请求，无 refresh 调用
      expect(dispatchSpy).not.toHaveBeenCalledWith(
        expect.objectContaining({ type: 'auth:session-expired' })
      )
      dispatchSpy.mockRestore()
    })

    it('有效 token 的正常请求不应触发任何续期逻辑', async () => {
      // Arrange
      apiClient.setToken('valid-token')

      mockFetch.mockResolvedValueOnce(
        createMockResponse({
          ok: true,
          json: () => Promise.resolve({ id: '123', is_anonymous: false }),
        })
      )

      // Act
      await apiClient.get('/api/v1/auth/me')

      // Assert: token 不变，只有一次 fetch 调用
      expect(getAuthToken()).toBe('valid-token')
      expect(mockFetch).toHaveBeenCalledTimes(1)
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
