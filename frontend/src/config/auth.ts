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

/**
 * 构造 SSO 登录跳转地址，附带当前来源以便登录后回跳。
 * callbackOrigin 含 VITE_APP_ROOT，使 IAM 回调落到 /ai-agent/sso-callback。
 */
export function buildSsoLoginUrl(returnPath: string): string {
  if (!RAW_SSO_LOGIN_URL) {
    return '/login'
  }
  const appRoot = (import.meta.env.VITE_APP_ROOT as string | undefined) ?? '/ai-agent'
  const normalizedRoot = appRoot.endsWith('/') ? appRoot.slice(0, -1) : appRoot
  const origin = typeof window !== 'undefined' ? window.location.origin : ''
  const callbackOrigin = encodeURIComponent(`${origin}${normalizedRoot}`)
  const normalizedReturn = returnPath.startsWith('/') ? returnPath : `/${returnPath}`
  const redirect = encodeURIComponent(`${origin}${normalizedReturn}`)
  const sep = RAW_SSO_LOGIN_URL.includes('?') ? '&' : '?'
  return `${RAW_SSO_LOGIN_URL}${sep}callbackOrigin=${callbackOrigin}&redirect=${redirect}`
}
