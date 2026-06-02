/**
 * 认证模式配置
 *
 * - local：本地邮箱密码 + JWT 登录（默认，开发环境）
 * - sso：经 giikin 单点登录；身份由 HiGress(giikin-auth-bridge) 经 guard_token Cookie 注入，
 *        前端不持有本地 token，未登录时跳转到 SSO 登录入口。
 * - hybrid：双通道，同时支持 SSO 与邮箱密码登录；Bearer JWT 优先，无 Bearer 才走网关 Header。
 *
 * 相关环境变量：
 * - VITE_AUTH_MODE: 'sso' | 'local' | 'hybrid'
 * - VITE_SSO_LOGIN_URL: SSO 登录入口（完整 URL 或同域路径），sso/hybrid 模式必填
 * - VITE_SSO_LOGOUT_URL: SSO 登出 API（可选，默认同域 /api/auth/logout，与 plus-ui 一致）
 */

export type AuthMode = 'sso' | 'local' | 'hybrid'

const RAW_AUTH_MODE = import.meta.env.VITE_AUTH_MODE ?? 'local'
export const AUTH_MODE: AuthMode =
  RAW_AUTH_MODE === 'sso' || RAW_AUTH_MODE === 'hybrid' ? RAW_AUTH_MODE : 'local'

/** 是否具备 SSO 能力（sso 或 hybrid） */
export const isSsoMode = AUTH_MODE !== 'local'

/** 是否为 hybrid 双通道模式 */
export const isHybridMode = AUTH_MODE === 'hybrid'

/** 是否展示本地邮箱密码登录表单 */
export const showLocalLogin = AUTH_MODE === 'local' || AUTH_MODE === 'hybrid'

const RAW_SSO_LOGIN_URL = import.meta.env.VITE_SSO_LOGIN_URL ?? ''
const RAW_SSO_LOGOUT_URL = import.meta.env.VITE_SSO_LOGOUT_URL ?? ''

/** sessionStorage：SSO 跳转 manage.giikin.com 前保存，回调后恢复路径 */
export const SSO_RETURN_PATH_KEY = 'ai_agent_sso_return_path'

/** sessionStorage：最近一次发起 SSO 跳转的时间戳，用于防止 401 死循环 */
export const SSO_ATTEMPT_AT_KEY = 'ai_agent_sso_attempt_at'

/** SSO 冷却期：此时间内 auth/me 仍 401 则展示错误页，不再自动跳 SSO */
export const SSO_COOLDOWN_MS = 120_000

/** SSO 最大连续尝试次数（跨页面，cookie 持久化）；超过后停止自动重定向，展示手动重试页 */
export const SSO_MAX_ATTEMPTS = 3

// ---------------------------------------------------------------------------
// 双存储层：sessionStorage + SameSite=Lax cookie
//
// 无痕模式下 sessionStorage 可能在跨域重定向链中被浏览器静默清理，
// cookie 作为可靠备份。读写均通过 dualStorage 抽象，避免重复模式。
// ---------------------------------------------------------------------------

function getCookie(name: string): string | null {
  const match = document.cookie.split('; ').find((c) => c.startsWith(`${name}=`))
  return match ? decodeURIComponent(match.slice(name.length + 1)) : null
}

function setCookie(name: string, value: string, maxAgeSec: number): void {
  document.cookie = `${name}=${encodeURIComponent(value)};path=/;max-age=${String(maxAgeSec)};SameSite=Lax`
}

function removeCookie(name: string): void {
  document.cookie = `${name}=;path=/;max-age=0;SameSite=Lax`
}

/**
 * 双存储对：写入时 sessionStorage + cookie 双写，
 * 读取时优先 sessionStorage、降级到 cookie，清理时同时清除。
 */
function dualStorage(sessionKey: string, cookieName: string, cookieMaxAgeSec: number) {
  return {
    write(value: string): void {
      try {
        sessionStorage.setItem(sessionKey, value)
      } catch {
        // 无痕模式可能抛 QuotaExceededError 或 SecurityError
      }
      setCookie(cookieName, value, cookieMaxAgeSec)
    },
    /** 优先 sessionStorage，降级到 cookie；不清理 */
    read(): string | null {
      try {
        return sessionStorage.getItem(sessionKey)
      } catch {
        // ignore
      }
      return getCookie(cookieName)
    },
    /** 一次性消费：读取并同时清理双存储 */
    consume(): string | null {
      let value: string | null = null
      try {
        value = sessionStorage.getItem(sessionKey)
        sessionStorage.removeItem(sessionKey)
      } catch {
        // ignore
      }
      // sessionStorage 已有值时跳过 cookie 读取，但仍需清理 cookie
      if (value !== null) {
        removeCookie(cookieName)
        return value
      }
      value = getCookie(cookieName)
      removeCookie(cookieName)
      return value
    },
    clear(): void {
      try {
        sessionStorage.removeItem(sessionKey)
      } catch {
        // ignore
      }
      removeCookie(cookieName)
    },
  }
}

const ssoAttemptStore = dualStorage(SSO_ATTEMPT_AT_KEY, 'ai_agent_sso_ts', 3600)
const ssoReturnPathStore = dualStorage(SSO_RETURN_PATH_KEY, 'ai_agent_sso_rp', 600)

// ---------------------------------------------------------------------------
// SSO 尝试计数器：纯 cookie 实现，跨页面重定向持久化。
// 用于断路器：防止 guard_token 始终无法建立时的无限重定向循环。
// ---------------------------------------------------------------------------

const SSO_ATTEMPT_COUNT_COOKIE = 'ai_agent_sso_cnt'

/** 读取 SSO 连续尝试次数 */
export function getSsoAttemptCount(): number {
  const raw = getCookie(SSO_ATTEMPT_COUNT_COOKIE)
  if (!raw) return 0
  const n = Number(raw)
  return Number.isFinite(n) ? n : 0
}

/** 递增 SSO 尝试计数并返回新值 */
export function incrementSsoAttemptCount(): number {
  const count = getSsoAttemptCount() + 1
  setCookie(SSO_ATTEMPT_COUNT_COOKIE, String(count), 3600)
  return count
}

/** 重置 SSO 尝试计数（登录成功后调用） */
export function resetSsoAttemptCount(): void {
  removeCookie(SSO_ATTEMPT_COUNT_COOKIE)
}

/**
 * 清除浏览器中可能已过期的 guard_token（HttpOnly，仅 IAM logout 可清）。
 * 用于 auth/me 401 且 Redis session 已失效时的自愈，避免 stale Cookie 阻塞 SSO。
 */
export async function clearStaleGiikinSession(): Promise<void> {
  try {
    await fetch(resolveSsoLogoutUrl(), { method: 'POST', credentials: 'include' })
  } catch {
    // 忽略网络错误，后续 SSO 仍会尝试
  }
}

export function markSsoAttempt(): void {
  ssoAttemptStore.write(String(Date.now()))
}

export function clearSsoAttempt(): void {
  ssoAttemptStore.clear()
  resetSsoAttemptCount()
}

export function isWithinSsoCooldown(): boolean {
  const raw = ssoAttemptStore.read()
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

  const attemptCount = incrementSsoAttemptCount()
  console.warn(`[SSO] initiateSsoLogin attempt #${String(attemptCount)}, returnPath=${returnPath}`)

  ssoReturnPathStore.write(returnPath)
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
 * 读取 SSO 返回路径：优先 sessionStorage，降级到 cookie。
 * 读取后自动清理（一次性消费）。
 */
export function consumeSsoReturnPath(): string | null {
  return ssoReturnPathStore.consume()
}

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
