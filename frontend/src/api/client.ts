/**
 * API Client
 *
 * 认证策略（优先级从高到低）：
 * 1. JWT Token (Authorization: Bearer) - 已登录用户
 * 2. Cookie (anonymous_user_id) - 匿名用户（浏览器自动发送）
 * 3. Header (X-Anonymous-User-Id) - 匿名用户备用方案（Cookie 丢失时）
 *
 * 状态管理：
 * - Token 和 anonymousUserId 由 authStore (Zustand) 统一管理
 * - apiClient 通过 authStore.getState() 获取认证信息
 * - 避免直接操作 localStorage，保持状态一致性
 *
 * 基于 Vite 的 API 客户端最佳实践：
 * - 开发环境：使用相对路径，通过 vite.config.ts 的 proxy 转发，自动解决 CORS
 * - 生产环境：配置 VITE_API_URL 环境变量，或前后端同域部署
 *
 * @example vite.config.ts 配置
 * ```ts
 * server: {
 *   proxy: {
 *     '/api': {
 *       target: 'http://localhost:8000',
 *       changeOrigin: true,
 *     },
 *   },
 * }
 * ```
 */

import {
  getAuthToken,
  getAnonymousUserId,
  setAuthToken,
  setAnonymousUserId,
  clearAuth,
  handleUnauthorized,
} from '@/stores/auth'

// 开发环境为空（使用 vite proxy），生产环境按需配置
const API_BASE_URL = (import.meta.env.VITE_API_URL as string | undefined) ?? ''

interface RequestOptions extends RequestInit {
  params?: Record<string, string | number | boolean | undefined>
}

class ApiClient {
  private baseUrl: string

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl
  }

  /**
   * 设置 JWT Token（委托给 authStore）
   */
  setToken(token: string | null): void {
    setAuthToken(token)
  }

  /**
   * 设置匿名用户 ID（委托给 authStore）
   * 用于 Cookie 丢失时的备用认证
   */
  setAnonymousUserId(id: string | null): void {
    setAnonymousUserId(id)
  }

  /**
   * 获取当前匿名用户 ID
   */
  getAnonymousUserId(): string | null {
    return getAnonymousUserId()
  }

  /**
   * 清除所有认证信息（用于登出）
   */
  clearAuth(): void {
    clearAuth()
  }

  /**
   * 构建请求 URL
   * - 有 baseUrl 时：构建完整 URL（生产环境）
   * - 无 baseUrl 时：返回相对路径（开发环境，由 vite proxy 转发）
   */
  private buildUrl(
    path: string,
    params?: Record<string, string | number | boolean | undefined>
  ): string {
    const queryString = this.buildQueryString(params)

    if (this.baseUrl) {
      const url = new URL(path, this.baseUrl)
      url.search = queryString
      return url.toString()
    }

    return queryString ? `${path}?${queryString}` : path
  }

  private buildQueryString(params?: Record<string, string | number | boolean | undefined>): string {
    if (!params) return ''
    const searchParams = new URLSearchParams()
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined) {
        searchParams.append(key, String(value))
      }
    }
    return searchParams.toString()
  }

  private async request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const { params, ...fetchOptions } = options

    const url = this.buildUrl(path, params)

    const defaultHeaders: Record<string, string> = {
      'Content-Type': 'application/json',
    }
    const customHeaders = options.headers as Record<string, string> | undefined
    const headers: Record<string, string> = customHeaders
      ? { ...defaultHeaders, ...customHeaders }
      : defaultHeaders

    // 从 authStore 获取认证信息
    const token = getAuthToken()
    const anonymousUserId = getAnonymousUserId()

    // 认证策略：优先使用 Token，其次使用匿名用户 ID
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    } else if (anonymousUserId) {
      // 没有 Token 时，添加匿名用户 ID 作为备用认证
      // 这在 Cookie 丢失时可以帮助后端识别用户
      headers['X-Anonymous-User-Id'] = anonymousUserId
    }

    const response = await fetch(url, {
      ...fetchOptions,
      headers,
      credentials: 'include', // 携带 Cookie，支持匿名用户隔离
    })

    // 从响应头中提取并保存 anonymous_user_id（如果存在）
    // 这样即使 Cookie 丢失，前端仍可通过 authStore 恢复身份
    const responseAnonymousId = response.headers.get('X-Anonymous-User-Id')
    if (responseAnonymousId && !token) {
      setAnonymousUserId(responseAnonymousId)
    }

    if (!response.ok) {
      // 401 错误时通过 authStore 清除可能无效的 token
      if (response.status === 401) {
        handleUnauthorized()
      }

      const error = (await response.json().catch(() => ({ message: 'Unknown error' }))) as {
        detail?: string
        message?: string
      }
      // 错误消息包含状态码，便于上层识别错误类型（如 401 未授权）
      const errorMessage = error.detail ?? error.message ?? 'Unknown error'
      throw new Error(`HTTP ${String(response.status)}: ${errorMessage}`)
    }

    return (await response.json()) as T
  }

  async get<T>(
    path: string,
    params?: Record<string, string | number | boolean | undefined>
  ): Promise<T> {
    return this.request<T>(path, { method: 'GET', params })
  }

  async post<T>(path: string, data?: unknown): Promise<T> {
    return this.request<T>(path, {
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    })
  }

  async postForm<T>(path: string, data: Record<string, string>): Promise<T> {
    const formData = new URLSearchParams()
    for (const [key, value] of Object.entries(data)) {
      formData.append(key, value)
    }

    return this.request<T>(path, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: formData.toString(),
    })
  }

  async put<T>(path: string, data?: unknown): Promise<T> {
    return this.request<T>(path, {
      method: 'PUT',
      body: data ? JSON.stringify(data) : undefined,
    })
  }

  async patch<T>(path: string, data?: unknown): Promise<T> {
    return this.request<T>(path, {
      method: 'PATCH',
      body: data ? JSON.stringify(data) : undefined,
    })
  }

  async delete<T>(path: string): Promise<T> {
    return this.request<T>(path, { method: 'DELETE' })
  }

  // SSE 流式请求（支持取消）
  async stream(
    path: string,
    data: unknown,
    onEvent: (event: { type: string; data: unknown }) => void,
    onError?: (error: Error) => void,
    onComplete?: () => void,
    signal?: AbortSignal
  ): Promise<void> {
    const url = this.buildUrl(path)

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    }

    // 从 authStore 获取认证信息
    const token = getAuthToken()
    const anonymousUserId = getAnonymousUserId()

    // 认证策略：优先使用 Token，其次使用匿名用户 ID
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    } else if (anonymousUserId) {
      headers['X-Anonymous-User-Id'] = anonymousUserId
    }

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers,
        body: JSON.stringify(data),
        signal, // 支持 AbortController 取消
        credentials: 'include', // 携带 Cookie，支持匿名用户隔离
      })

      // 从响应头中提取并保存 anonymous_user_id
      const responseAnonymousId = response.headers.get('X-Anonymous-User-Id')
      if (responseAnonymousId && !token) {
        setAnonymousUserId(responseAnonymousId)
      }

      if (!response.ok) {
        throw new Error(`HTTP ${String(response.status)}`)
      }

      const reader = response.body?.getReader()
      if (!reader) {
        throw new Error('No response body')
      }

      const decoder = new TextDecoder()
      let buffer = ''

      // eslint-disable-next-line @typescript-eslint/no-unnecessary-condition
      while (true) {
        const { done, value } = await reader.read()

        if (done) {
          onComplete?.()
          break
        }

        // When done is false, value is guaranteed to be defined
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        const lastLine = lines.pop()
        buffer = lastLine ?? ''

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const jsonStr = line.slice(6)
            if (jsonStr === '[DONE]') {
              onComplete?.()
              return
            }
            try {
              const event = JSON.parse(jsonStr) as { type: string; data: unknown }
              onEvent(event)
            } catch {
              // Ignore JSON parse errors
            }
          }
        }
      }
    } catch (error) {
      onError?.(error as Error)
    }
  }
}

export const apiClient = new ApiClient(API_BASE_URL)
