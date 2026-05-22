/**
 * 判断 HTTP 401 是否应触发「全局登录态失效」（清 token / session-expired）。
 *
 * 约定：
 * - 后端业务无权限 → 403（PermissionDeniedError / TeamPermissionDeniedError）
 * - 401 → 未认证或 JWT/refresh 失效
 * - 部分 401（如 Authentication required）表示当前资源须登录，不代表已有 token 失效
 */

import { parseFastApiDetail } from '@/lib/fastapi-error-detail'

function errorDetailLower(body: unknown): string {
  if (typeof body !== 'object' || body === null || !('detail' in body)) {
    return ''
  }
  return (parseFastApiDetail((body as { detail: unknown }).detail) ?? '').toLowerCase()
}

/** 401 但不代表 JWT 失效：勿 refresh、勿清全局会话 */
const BENIGN_UNAUTHORIZED_DETAIL_PATTERNS = [
  'authentication required',
  'permission denied',
  'required role',
  'anonymous users cannot',
  'viewer accounts are read-only',
  'user context required',
  'gateway grant',
  'missing gateway',
  'platform admin',
  'forbidden',
  '无权',
] as const

/**
 * 是否应将此次 401 视为「会话失效」并尝试 refresh / 派发 session-expired。
 *
 * @param hadToken 请求是否携带了 access token（无 token 的 401 仅影响当前请求）
 */
export function shouldInvalidateGlobalSession(
  status: number,
  body: unknown,
  hadToken: boolean
): boolean {
  if (status !== 401 || !hadToken) {
    return false
  }
  const detail = errorDetailLower(body)
  if (detail.length === 0) {
    // 无 detail 时保守按 token 失效处理（与历史行为一致）
    return true
  }
  return !BENIGN_UNAUTHORIZED_DETAIL_PATTERNS.some((pattern) => detail.includes(pattern))
}
