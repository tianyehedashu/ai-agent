/**
 * 认证模式配置
 *
 * - local：本地邮箱密码 + JWT 登录（默认，开发环境）
 * - sso：经 giikin 单点登录；身份由 HiGress(giikin-auth-bridge) 经 guard_token Cookie 注入，
 *        前端不持有本地 token，未登录时跳转到 SSO 登录入口。
 *
 * 相关环境变量：
 * - VITE_AUTH_MODE: 'sso' | 'local'
 * - VITE_SSO_LOGIN_URL: SSO 登录入口（完整 URL 或同域路径），sso 模式必填
 * - VITE_SSO_LOGOUT_URL: SSO 登出 API（可选，默认同域 /api/auth/logout，与 plus-ui 一致）
 */

export type AuthMode = 'sso' | 'local'

export const AUTH_MODE: AuthMode = import.meta.env.VITE_AUTH_MODE === 'sso' ? 'sso' : 'local'

export const isSsoMode = AUTH_MODE === 'sso'

const RAW_SSO_LOGIN_URL = import.meta.env.VITE_SSO_LOGIN_URL ?? ''
const RAW_SSO_LOGOUT_URL = import.meta.env.VITE_SSO_LOGOUT_URL ?? ''

/** sessionStorage：SSO 跳转 manage.giikin.com 前保存，回调后恢复路径 */
export const SSO_RETURN_PATH_KEY = 'ai_agent_sso_return_path'

/** sessionStorage：最近一次发起 SSO 跳转的时间戳，用于防止 401 死循环 */
export const SSO_ATTEMPT_AT_KEY = 'ai_agent_sso_attempt_at'

/** SSO 冷却期：此时间内 auth/me 仍 401 则展示错误页，不再自动跳 SSO */
export const SSO_COOLDOWN_MS = 120_000

export function markSsoAttempt(): void {
  if (typeof sessionStorage === 'undefined') {
    return
  }
  sessionStorage.setItem(SSO_ATTEMPT_AT_KEY, String(Date.now()))
}

export function clearSsoAttempt(): void {
  if (typeof sessionStorage === 'undefined') {
    return
  }
  sessionStorage.removeItem(SSO_ATTEMPT_AT_KEY)
}

export function isWithinSsoCooldown(): boolean {
  if (typeof sessionStorage === 'undefined') {
    return false
  }
  const raw = sessionStorage.getItem(SSO_ATTEMPT_AT_KEY)
  if (!raw) {
    return false
  }
  const ts = Number(raw)
  if (!Number.isFinite(ts)) {
    return false
  }
  return Date.now() - ts < SSO_COOLDOWN_MS
}

/**
 * guard_token 为 HttpOnly，JS 无法读取；不可用于判断是否已登录。
 * @deprecated 仅保留兼容；请用 auth/me + SSO 冷却期判断。
 */
export function hasGuardTokenCookie(): boolean {
  return false
}

function normalizeAppRoot(): string {
  const appRoot = (import.meta.env.VITE_APP_ROOT as string | undefined) ?? '/ai-agent'
  if (!appRoot || appRoot === '/') {
    return ''
  }
  return appRoot.endsWith('/') ? appRoot.slice(0, -1) : appRoot
}

interface SsoBindingResponse {
  code?: number
  msg?: string
  data?: string
}

/**
 * 构造 IAM binding API URL（GET /auth/binding/company_sso）。
 * 该接口返回 JSON `{ code, data: authorizeUrl }`，不能直接浏览器导航。
 */
export function buildSsoBindingApiUrl(): URL | null {
  if (!RAW_SSO_LOGIN_URL.trim()) {
    return null
  }
  const origin = typeof window !== 'undefined' ? window.location.origin : 'http://localhost'
  const url = new URL(RAW_SSO_LOGIN_URL.trim(), origin)
  const appRoot = normalizeAppRoot()
  url.searchParams.set('callbackOrigin', `${origin}${appRoot}`)
  if (!url.searchParams.has('domain')) {
    url.searchParams.set('domain', typeof window !== 'undefined' ? window.location.host : 'admin')
  }
  return url
}

/**
 * 发起 SSO 登录：先请求 binding API 取 authorizeUrl，再跳转 manage.giikin.com（与 plus-ui 一致）。
 */
export async function initiateSsoLogin(returnPath: string): Promise<void> {
  const bindingUrl = buildSsoBindingApiUrl()
  if (!bindingUrl) {
    window.location.href = '/login'
    return
  }

  sessionStorage.setItem(SSO_RETURN_PATH_KEY, returnPath)
  markSsoAttempt()

  const response = await fetch(bindingUrl.toString(), { credentials: 'include' })
  const body = (await response.json()) as SsoBindingResponse

  if (body.code === 200 && typeof body.data === 'string' && body.data.trim()) {
    window.location.href = body.data.trim()
    return
  }

  throw new Error(body.msg ?? 'SSO 登录初始化失败')
}

/**
 * @deprecated 请使用 {@link initiateSsoLogin}；binding 接口返回 JSON 而非 302。
 */
export function buildSsoLoginUrl(returnPath: string): string {
  const bindingUrl = buildSsoBindingApiUrl()
  if (!bindingUrl) {
    return '/login'
  }
  const normalizedReturn = returnPath.startsWith('/') ? returnPath : `/${returnPath}`
  bindingUrl.searchParams.set('redirect', `${window.location.origin}${normalizedReturn}`)
  return bindingUrl.toString()
}

/** 生产默认同域 IAM 登出（清除 guard_token + Redis 会话） */
const DEFAULT_SSO_LOGOUT_URL = 'http://gateway.giimallai.com/api/auth/logout'

/**
 * IAM 登出地址：SSO 模式须调用此接口才能真正清除 guard_token Cookie。
 */
export function resolveSsoLogoutUrl(): string {
  if (RAW_SSO_LOGOUT_URL.trim()) {
    return RAW_SSO_LOGOUT_URL.trim()
  }
  if (typeof window !== 'undefined') {
    return `${window.location.origin}/api/auth/logout`
  }
  return DEFAULT_SSO_LOGOUT_URL
}
