/**
 * 模型「归属」列：个人 / 团队名 / 系统。
 */

import type React from 'react'

import {
  CredentialScopeBadge,
  CredentialTeamBadge,
} from '@/features/gateway-credentials/credential-scope-display'
import {
  credentialScopeLabel,
  credentialTeamLabel,
} from '@/features/gateway-credentials/credential-scope-labels'
import { ListCellText } from '@/features/gateway-models/list/list-cell-text'
import type { GatewayModelListScope } from '@/features/gateway-models/list/types'

export interface ModelAffiliationCellProps {
  scope: GatewayModelListScope
  teamId?: string | null
  teamNameById: Map<string, string>
  /** 表格列布局：纯文本，不用 Badge */
  plain?: boolean
}

function affiliationText(
  scope: GatewayModelListScope,
  teamId: string | null | undefined,
  teamNameById: Map<string, string>
): string {
  if (scope === 'personal') return credentialScopeLabel('user')
  if (scope === 'team') return credentialTeamLabel(teamId, teamNameById)
  return credentialScopeLabel('system')
}

export function ModelAffiliationCell({
  scope,
  teamId,
  teamNameById,
  plain = false,
}: ModelAffiliationCellProps): React.JSX.Element {
  const label = affiliationText(scope, teamId, teamNameById)

  if (plain) {
    return <ListCellText value={label} mono={false} />
  }

  if (scope === 'personal') {
    return <CredentialScopeBadge scope="user" />
  }
  if (scope === 'team') {
    return <CredentialTeamBadge tenantId={teamId} teamNameById={teamNameById} />
  }
  return <CredentialScopeBadge scope="system" />
}
