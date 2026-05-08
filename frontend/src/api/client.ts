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
  getRefreshToken,
  getAnonymousUserId,
  setAuthToken,
  setRefreshToken,
  setAnonymousUserId,
  clearAuth,
  handleUnauthorized,
} from '@/stores/auth'

// 开发环境为空（使用 vite proxy），生产环境按需配置
const API_BASE_URL = (import.meta.env.VITE_API_URL as string | undefined) ?? ''

interface RequestOptions extends RequestInit {
  params?: Record<string, string | number | boolean | undefined>
}

/** API 错误 - 携带 HTTP 状态码，便于上层精确判断 */
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

class ApiClient {
  private baseUrl: string

  /** 正在进行中的 refresh 请求（避免并发重复刷新） */
  private refreshPromise: Promise<boolean> | null = null

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl
  }

  /**
   * 尝试使用 refresh_token 获取新的 token pair
   * 返回 true 表示续期成功，false 表示需要重新登录
   *
   * 注意：使用原生 fetch 而非 this.request()，避免递归 401 处理
   */
  private async tryRefresh(): Promise<boolean> {
    // 避免并发 refresh 请求
    if (this.refreshPromise) return this.refreshPromise

    const refreshToken = getRefreshToken()
    if (!refreshToken) return false

    this.refreshPromise = (async () => {
      try {
        const url = this.buildUrl('/api/v1/auth/token/refresh')
        const response = await fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: refreshToken }),
          credentials: 'include',
        })

        if (!response.ok) return false

        const data = (await response.json()) as {
          access_token: string
          refresh_token: string
        }
        setAuthToken(data.access_token)
        setRefreshToken(data.refresh_token)
        return true
      } catch {
        return false
      } finally {
        this.refreshPromise = null
      }
    })()

    return this.refreshPromise
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

  private async request<T>(
    path: string,
    options: RequestOptions = {},
    _retried = false
  ): Promise<T> {
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
      headers['X-Anonymous-User-Id'] = anonymousUserId
    }

    const response = await fetch(url, {
      ...fetchOptions,
      headers,
      credentials: 'include',
    })

    // 从响应头中提取并保存 anonymous_user_id
    const responseAnonymousId = response.headers.get('X-Anonymous-User-Id')
    if (responseAnonymousId && !token) {
      setAnonymousUserId(responseAnonymousId)
    }

    if (!response.ok) {
      if (response.status === 401) {
        const hadToken = !!token

        // 401 且未重试过：尝试用 refresh_token 自动续期
        if (hadToken && !_retried) {
          const refreshed = await this.tryRefresh()
          if (refreshed) {
            return this.request<T>(path, options, true)
          }
        }

        // refresh 失败或无 token：清除状态并通知
        handleUnauthorized()
        if (hadToken) {
          window.dispatchEvent(new Event('auth:session-expired'))
        }
      }

      const error = (await response.json().catch(() => ({ message: 'Unknown error' }))) as {
        detail?: string
        message?: string
      }
      throw new ApiError(response.status, error.detail ?? error.message ?? 'Unknown error')
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

  /**
   * 上传文件（multipart/form-data），不设置 Content-Type，由浏览器自动带 boundary
   */
  async upload<T>(path: string, formData: FormData): Promise<T> {
    const url = this.buildUrl(path)
    const headers: Record<string, string> = {}
    const token = getAuthToken()
    const anonymousUserId = getAnonymousUserId()
    if (token) headers['Authorization'] = `Bearer ${token}`
    else if (anonymousUserId) headers['X-Anonymous-User-Id'] = anonymousUserId

    const response = await fetch(url, {
      method: 'POST',
      headers,
      body: formData,
      credentials: 'include',
    })

    const responseAnonymousId = response.headers.get('X-Anonymous-User-Id')
    if (responseAnonymousId && !token) {
      setAnonymousUserId(responseAnonymousId)
    }

    if (!response.ok) {
      const error = (await response.json().catch(() => ({ detail: 'Unknown error' }))) as {
        detail?: string
      }
      throw new ApiError(response.status, error.detail ?? 'Upload failed')
    }
    return response.json() as Promise<T>
  }

  // SSE 流式请求（支持取消）
  async stream(
    path: string,
    data: unknown,
    onEvent: (event: { type: string; data: unknown }) => void,
    onError?: (error: Error) => void,
    onComplete?: () => void,
    signal?: AbortSignal,
    _retried = false
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
        signal,
        credentials: 'include',
      })

      // 从响应头中提取并保存 anonymous_user_id
      const responseAnonymousId = response.headers.get('X-Anonymous-User-Id')
      if (responseAnonymousId && !token) {
        setAnonymousUserId(responseAnonymousId)
      }

      if (!response.ok) {
        if (response.status === 401) {
          const hadToken = !!token

          // 尝试 refresh 后重试一次
          if (hadToken && !_retried) {
            const refreshed = await this.tryRefresh()
            if (refreshed) {
              await this.stream(path, data, onEvent, onError, onComplete, signal, true)
              return
            }
          }

          handleUnauthorized()
          if (hadToken) {
            window.dispatchEvent(new Event('auth:session-expired'))
          }
        }
        throw new ApiError(response.status, `HTTP ${String(response.status)}`)
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
