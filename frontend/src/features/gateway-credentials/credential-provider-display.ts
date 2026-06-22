/**
 * 凭据「提供者」列展示（列表 / 摘要）。
 */

import type { CredentialSummary, ProviderCredential } from '@/api/gateway'

type CredentialProviderFields = Pick<
  ProviderCredential | CredentialSummary,
  'created_by_label' | 'scope' | 'is_config_managed'
>

export function credentialProviderLabel(credential: CredentialProviderFields | undefined): string {
  const label = credential?.created_by_label?.trim()
  if (label) return label
  if (credential?.scope === 'system') {
    return credential.is_config_managed ? '平台（配置同步）' : '平台'
  }
  if (credential?.scope === 'user') return '个人'
  return '—'
}
