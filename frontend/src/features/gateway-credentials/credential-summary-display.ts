/**
 * 凭据摘要展示（纯 label；深链权限见 credential-permissions.ts）。
 */

import type { CredentialSummary } from '@/api/gateway'

export { canLinkToCredentialDetail } from './credential-permissions'

export function credentialSummaryLabel(
  summary: CredentialSummary | undefined,
  credentialId: string
): string {
  if (summary?.name) return summary.name
  const short = credentialId.length > 8 ? `${credentialId.slice(0, 8)}…` : credentialId
  return `未知凭据 (${short})`
}
