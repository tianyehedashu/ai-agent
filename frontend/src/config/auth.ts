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
 */

export type AuthMode = 'sso' | 'local'

export const AUTH_MODE: AuthMode = import.meta.env.VITE_AUTH_MODE === 'sso' ? 'sso' : 'local'

export const isSsoMode = AUTH_MODE === 'sso'

const RAW_SSO_LOGIN_URL = import.meta.env.VITE_SSO_LOGIN_URL ?? ''

/**
 * 构造 SSO 登录跳转地址，附带当前来源以便登录后回跳。
 * 未配置 VITE_SSO_LOGIN_URL 时回退到本地登录路由（避免死循环）。
 */
export function buildSsoLoginUrl(returnPath: string): string {
  if (!RAW_SSO_LOGIN_URL) {
    return '/login'
  }
  const origin = typeof window !== 'undefined' ? window.location.origin : ''
  const callbackOrigin = encodeURIComponent(origin)
  const redirect = encodeURIComponent(origin + returnPath)
  const sep = RAW_SSO_LOGIN_URL.includes('?') ? '&' : '?'
  return `${RAW_SSO_LOGIN_URL}${sep}callbackOrigin=${callbackOrigin}&redirect=${redirect}`
}
