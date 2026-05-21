/**
 * 凭据摘要展示与深链 gating（团队模型 / 凭据筛选 banner 共用）。
 */

import type { CredentialSummary } from '@/api/gateway'

export function credentialSummaryLabel(
  summary: CredentialSummary | undefined,
  credentialId: string
): string {
  if (summary?.name) return summary.name
  const short = credentialId.length > 8 ? `${credentialId.slice(0, 8)}…` : credentialId
  return `未知凭据 (${short})`
}

/** 团队 admin+ 可打开凭据详情；system 凭据仅平台管理员 */
export function canLinkToCredentialDetail(
  summary: CredentialSummary | undefined,
  isAdmin: boolean,
  isPlatformAdmin: boolean
): boolean {
  if (!summary || !isAdmin) return false
  if (summary.scope === 'system') return isPlatformAdmin
  return true
}
