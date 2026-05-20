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
