/**
 * API Client
 *
 * 认证策略：
 * - local 模式：JWT Token (Authorization: Bearer)，token 由 authStore 管理。
 * - sso 模式：身份由 HiGress(giikin-auth-bridge) 经 guard_token Cookie 注入，
 *   前端无本地 token，请求统一携带 Cookie（credentials: 'include'）。
 *
 * 状态管理：
 * - Token 由 authStore (Zustand) 统一管理
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
 *       // 开发环境不透传 Cookie（鉴权走 Header），避免 localhost Cookie 膨胀导致 Vite 431
 *     },
 *   },
 * }
 * ```
 */

import { ApiError } from '@/api/errors'
import { API_V1 } from '@/api/paths'
import { parseApiErrorBody, messageFromApiErrorBody } from '@/lib/fastapi-error-detail'
import { shouldInvalidateGlobalSession } from '@/lib/session-invalidation'
import {
  getAuthToken,
  getRefreshToken,
  setAuthToken,
  setRefreshToken,
  clearAuth,
} from '@/stores/auth'
// 开发环境为空（使用 vite proxy），生产环境按需配置
const API_BASE_URL = (import.meta.env.VITE_API_URL as string | undefined) ?? ''

export type ApiQueryParamValue = string | number | boolean | undefined | string[]

interface RequestOptions extends RequestInit {
  params?: Record<string, ApiQueryParamValue>
}

export { ApiError } from '@/api/errors'

async function parseResponseBody<T>(response: Response): Promise<T> {
  if (response.status === 204 || response.status === 205) {
    return undefined as T
  }
  const text = await response.text()
  if (!text.trim()) {
    return undefined as T
  }
  return JSON.parse(text) as T
}

class ApiClient {
  private baseUrl: string

  /** 正在进行中的 refresh 请求（避免并发重复刷新） */
  private refreshPromise: Promise<boolean> | null = null

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl
  }

  /** refresh 已失败或重试后仍 401：清会话并通知 AuthProvider */
  private failGlobalSession(hadToken: boolean): void {
    if (!hadToken) {
      return
    }
    clearAuth()
    window.dispatchEvent(new Event('auth:session-expired'))
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
        const url = this.buildUrl(`${API_V1}/auth/token/refresh`)
        const response = await fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: refreshToken }),
          credentials: 'include',
        })

        if (!response.ok) {
          if (response.status === 401) {
            clearAuth()
          }
          return false
        }

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
  private buildUrl(path: string, params?: Record<string, ApiQueryParamValue>): string {
    const queryString = this.buildQueryString(params)

    if (this.baseUrl) {
      const url = new URL(path, this.baseUrl)
      url.search = queryString
      return url.toString()
    }

    return queryString ? `${path}?${queryString}` : path
  }

  /** 将 fetch/SSE 底层错误转为可读文案（含 Higress/HTTPS 常见原因） */
  private normalizeStreamNetworkError(error: unknown, url: string): Error {
    if (error instanceof DOMException && error.name === 'AbortError') {
      return error
    }
    if (error instanceof ApiError) {
      return error
    }
    const raw = error instanceof Error ? error.message : String(error)
    const lower = raw.toLowerCase()
    const isNetwork =
      lower.includes('network') ||
      lower.includes('failed to fetch') ||
      lower.includes('load failed') ||
      lower.includes('networkerror')
    if (!isNetwork) {
      return error instanceof Error ? error : new Error(raw)
    }
    let hint =
      '请确认使用与页面相同的协议访问（本环境 HTTP 可用、HTTPS 可能未开通），并检查网关是否将 /ai-agent/api 正确转发且 SSE 超时足够长。'
    if (typeof window !== 'undefined') {
      try {
        const parsed = new URL(url, window.location.origin)
        if (parsed.protocol === 'https:' && window.location.protocol === 'http:') {
          hint = '页面为 HTTP，但 API 指向 HTTPS，请清空 VITE_API_URL 或改为 HTTP。'
        }
      } catch {
        // ignore invalid URL
      }
    }
    return new Error(`网络连接失败（${raw}）。${hint}`)
  }

  private async errorFromResponse(response: Response): Promise<ApiError> {
    const errorBody: unknown = await response.json().catch(() => ({ message: 'Unknown error' }))
    const fallback =
      typeof errorBody === 'object' &&
      errorBody !== null &&
      'detail' in errorBody &&
      typeof (errorBody as { detail: unknown }).detail === 'string'
        ? (errorBody as { detail: string }).detail
        : typeof errorBody === 'object' &&
            errorBody !== null &&
            'message' in errorBody &&
            typeof (errorBody as { message: unknown }).message === 'string'
          ? (errorBody as { message: string }).message
          : `HTTP ${String(response.status)}`
    const parsed = parseApiErrorBody(errorBody, fallback)
    return new ApiError(response.status, parsed.message, {
      code: parsed.code,
      title: parsed.title,
      errors: parsed.errors,
      extra: parsed.extra,
    })
  }

  private buildQueryString(params?: Record<string, ApiQueryParamValue>): string {
    if (!params) return ''
    const searchParams = new URLSearchParams()
    for (const [key, value] of Object.entries(params)) {
      if (value === undefined) continue
      if (Array.isArray(value)) {
        for (const item of value) {
          searchParams.append(key, item)
        }
        continue
      }
      searchParams.append(key, String(value))
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

    // local 模式携带 JWT；sso 模式靠 Cookie（credentials: 'include'）
    const token = getAuthToken()
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }

    const response = await fetch(url, {
      ...fetchOptions,
      headers,
      credentials: 'include',
    })

    if (!response.ok) {
      const errorBody: unknown = await response.json().catch(() => ({ message: 'Unknown error' }))

      if (response.status === 401) {
        const hadToken = !!token
        if (shouldInvalidateGlobalSession(401, errorBody, hadToken) && hadToken) {
          if (!_retried) {
            const refreshed = await this.tryRefresh()
            if (refreshed) {
              return this.request<T>(path, options, true)
            }
          }
          this.failGlobalSession(true)
        }
      }

      const fallback =
        typeof errorBody === 'object' &&
        errorBody !== null &&
        'message' in errorBody &&
        typeof (errorBody as { message: unknown }).message === 'string'
          ? (errorBody as { message: string }).message
          : 'Unknown error'
      const parsed = parseApiErrorBody(errorBody, fallback)
      throw new ApiError(response.status, parsed.message, {
        code: parsed.code,
        title: parsed.title,
        errors: parsed.errors,
        extra: parsed.extra,
      })
    }

    return parseResponseBody<T>(response)
  }

  async get<T>(path: string, params?: Record<string, ApiQueryParamValue>): Promise<T> {
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
    if (token) headers['Authorization'] = `Bearer ${token}`

    const response = await fetch(url, {
      method: 'POST',
      headers,
      body: formData,
      credentials: 'include',
    })

    if (!response.ok) {
      const errorBody: unknown = await response
        .json()
        .catch(() => ({ detail: 'Unknown error' }) as const)
      const message = messageFromApiErrorBody(errorBody, 'Upload failed')
      throw new ApiError(response.status, message)
    }
    return parseResponseBody<T>(response)
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

    // local 模式携带 JWT；sso 模式靠 Cookie
    const token = getAuthToken()
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers,
        body: JSON.stringify(data),
        signal,
        credentials: 'include',
      })

      if (!response.ok) {
        if (response.status === 401) {
          const hadToken = !!token
          if (shouldInvalidateGlobalSession(401, undefined, hadToken) && hadToken) {
            if (!_retried) {
              const refreshed = await this.tryRefresh()
              if (refreshed) {
                await this.stream(path, data, onEvent, onError, onComplete, signal, true)
                return
              }
            }
            this.failGlobalSession(true)
          }
        }
        throw await this.errorFromResponse(response)
      }

      const reader = response.body?.getReader()
      if (!reader) {
        throw new Error('No response body')
      }

      const decoder = new TextDecoder()
      let buffer = ''

      try {
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
      } finally {
        reader.releaseLock()
      }
    } catch (error) {
      const normalized = this.normalizeStreamNetworkError(error, url)
      if (normalized instanceof DOMException && normalized.name === 'AbortError') {
        return
      }
      onError?.(normalized)
    }
  }
}

export const apiClient = new ApiClient(API_BASE_URL)
