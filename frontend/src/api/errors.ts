/** RFC 7807 字段级错误项 */
export interface FieldError {
  loc: (string | number)[]
  msg: string
  type: string
}

export interface ParsedApiError {
  message: string
  code?: string
  title?: string
  errors?: FieldError[]
  extra?: Record<string, unknown>
}

/** API 错误 - 携带 HTTP 状态码与 RFC 7807 结构化字段 */
export class ApiError extends Error {
  readonly status: number
  readonly code?: string
  readonly title?: string
  readonly errors?: FieldError[]
  readonly extra?: Record<string, unknown>

  constructor(
    status: number,
    message: string,
    options?: {
      code?: string
      title?: string
      errors?: FieldError[]
      extra?: Record<string, unknown>
    }
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = options?.code
    this.title = options?.title
    this.errors = options?.errors
    this.extra = options?.extra
  }
}
