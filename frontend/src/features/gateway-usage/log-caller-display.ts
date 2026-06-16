/** 调用人（用户）在调用日志表格中的展示文案。 */

import type { GatewayLogItem } from '@/api/gateway/logs'

export type LogCallerDisplayFields = Pick<GatewayLogItem, 'user_email_snapshot' | 'user_id'>

export function logCallerDisplayText(item: LogCallerDisplayFields): string {
  const email = item.user_email_snapshot?.trim()
  if (email) return email
  const userId = item.user_id?.trim()
  if (userId) return userId
  return '—'
}

export function logCallerDisplayTitle(item: LogCallerDisplayFields): string | undefined {
  const email = item.user_email_snapshot?.trim()
  const userId = item.user_id?.trim()
  if (email && userId) return `${email} · ${userId}`
  return email ?? userId ?? undefined
}
