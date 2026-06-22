/**
 * 凭据列表「提供者」列。
 */

import type React from 'react'

import type { CredentialSummary, ProviderCredential } from '@/api/gateway'
import { credentialProviderLabel } from '@/features/gateway-credentials/credential-provider-display'

export interface CredentialProviderCellProps {
  credential: Pick<
    ProviderCredential | CredentialSummary,
    'created_by_label' | 'scope' | 'is_config_managed'
  >
}

export function CredentialProviderCell({
  credential,
}: CredentialProviderCellProps): React.JSX.Element {
  const label = credentialProviderLabel(credential)
  return (
    <span className="text-xs text-foreground" title={label}>
      {label}
    </span>
  )
}
