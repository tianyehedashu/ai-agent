/**
 * 凭据作用域 / 归属 / 可见性 Badge 组件。
 */

import type React from 'react'

import type { ProviderCredential } from '@/api/gateway'
import { Badge } from '@/components/ui/badge'
import {
  credentialScopeLabel,
  credentialTeamLabel,
} from '@/features/gateway-credentials/credential-scope-labels'

export function CredentialScopeBadge({
  scope,
}: Readonly<{ scope: ProviderCredential['scope'] | null | undefined }>): React.JSX.Element {
  return (
    <Badge variant="outline" className="text-[10px] font-normal">
      {credentialScopeLabel(scope)}
    </Badge>
  )
}

export function CredentialTeamBadge({
  tenantId,
  teamNameById,
}: Readonly<{
  tenantId: string | null | undefined
  teamNameById: Map<string, string>
}>): React.JSX.Element {
  const label = credentialTeamLabel(tenantId, teamNameById)
  return (
    <Badge variant="secondary" className="text-[10px] font-normal" title={tenantId ?? undefined}>
      {label}
    </Badge>
  )
}

export function CredentialVisibilityBadge({
  visibility,
}: Readonly<{ visibility: ProviderCredential['visibility'] }>): React.JSX.Element {
  const restricted = visibility === 'restricted'
  return (
    <Badge variant={restricted ? 'destructive' : 'secondary'} className="text-[10px] font-normal">
      {restricted ? '受限' : '公开 · 全平台'}
    </Badge>
  )
}
