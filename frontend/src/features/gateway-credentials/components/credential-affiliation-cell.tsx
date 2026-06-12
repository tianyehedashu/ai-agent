/**
 * 凭据「归属」列：个人 / 团队名 / 系统。
 */

import type React from 'react'

import type { CredentialSummary, ProviderCredential } from '@/api/gateway'
import {
  CredentialScopeBadge,
  CredentialTeamBadge,
  CredentialVisibilityBadge,
} from '@/features/gateway-credentials/credential-scope-display'

export interface CredentialAffiliationCellProps {
  scope: ProviderCredential['scope'] | CredentialSummary['scope']
  tenantId?: string | null
  visibility?: ProviderCredential['visibility']
  teamNameById: Map<string, string>
  compact?: boolean
}

export function CredentialAffiliationCell({
  scope,
  tenantId,
  visibility,
  teamNameById,
  compact = false,
}: CredentialAffiliationCellProps): React.JSX.Element {
  if (scope === 'user') {
    return <CredentialScopeBadge scope="user" />
  }
  if (scope === 'team') {
    return <CredentialTeamBadge tenantId={tenantId} teamNameById={teamNameById} />
  }
  if (scope === 'system') {
    return (
      <div className={compact ? 'flex flex-wrap items-center gap-1' : 'flex flex-col gap-0.5'}>
        <CredentialScopeBadge scope="system" />
        {visibility ? <CredentialVisibilityBadge visibility={visibility} /> : null}
      </div>
    )
  }
  return <span className="text-xs text-muted-foreground">—</span>
}
