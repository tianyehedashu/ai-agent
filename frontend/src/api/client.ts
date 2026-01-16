/**
 * API Client
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

// 开发环境为空（使用 vite proxy），生产环境按需配置
const API_BASE_URL = import.meta.env.VITE_API_URL ?? ''

interface RequestOptions extends RequestInit {
  params?: Record<string, string | number | boolean | undefined>
}

class ApiClient {
  private baseUrl: string
  private token: string | null = null

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl
    this.token = localStorage.getItem('auth_token')
  }

  setToken(token: string | null): void {
    this.token = token
    if (token) {
      localStorage.setItem('auth_token', token)
    } else {
      localStorage.removeItem('auth_token')
    }
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

  private buildQueryString(
    params?: Record<string, string | number | boolean | undefined>
  ): string {
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

    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`
    }

    const response = await fetch(url, {
      ...fetchOptions,
      headers,
    })

    if (!response.ok) {
      const error = (await response.json().catch(() => ({ message: 'Unknown error' }))) as {
        detail?: string
        message?: string
      }
      throw new Error(error.detail ?? error.message ?? `HTTP ${String(response.status)}`)
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

  async put<T>(path: string, data?: unknown): Promise<T> {
    return this.request<T>(path, {
      method: 'PUT',
      body: data ? JSON.stringify(data) : undefined,
    })
  }

  async delete<T>(path: string): Promise<T> {
    return this.request<T>(path, { method: 'DELETE' })
  }

  // SSE 流式请求
  async stream(
    path: string,
    data: unknown,
    onEvent: (event: { type: string; data: unknown }) => void,
    onError?: (error: Error) => void,
    onComplete?: () => void
  ): Promise<void> {
    const url = this.buildUrl(path)

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    }

    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`
    }

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers,
        body: JSON.stringify(data),
      })

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
