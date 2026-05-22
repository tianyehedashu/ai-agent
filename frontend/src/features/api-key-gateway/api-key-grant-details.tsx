/**
 * API Key 卡片内 Gateway grant 详情
 */

import type React from 'react'

import { Link } from 'react-router-dom'

import { Badge } from '@/components/ui/badge'
import type { ApiKeyGatewayGrant } from '@/types/api-key'

import { GrantEntitlementsSummary } from './grant-entitlements-summary'

function formatLimit(value: number | null): string {
  return value === null ? '∞' : String(value)
}

interface ApiKeyGrantDetailsProps {
  grants: ApiKeyGatewayGrant[]
  resolveTeamLabel: (teamId: string) => string
}

export function ApiKeyGrantDetails({
  grants,
  resolveTeamLabel,
}: ApiKeyGrantDetailsProps): React.ReactElement | null {
  if (grants.length === 0) return null

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-medium text-muted-foreground">Gateway 团队授权</span>
        <Link to="/gateway/guide" className="text-xs text-primary hover:underline">
          调用说明
        </Link>
      </div>
      {grants.map((grant) => (
        <div key={grant.id} className="rounded border bg-muted/30 px-3 py-2 text-xs">
          <div className="mb-1 flex flex-wrap items-center gap-2">
            <Badge variant="outline">{resolveTeamLabel(grant.team_id)}</Badge>
            <span className="text-muted-foreground">
              RPM {formatLimit(grant.rpm_limit)} / TPM {formatLimit(grant.tpm_limit)}
            </span>
          </div>
          <div className="text-muted-foreground">
            模型: {grant.allowed_models.length === 0 ? '全部' : grant.allowed_models.join(', ')}
          </div>
          <div className="text-muted-foreground">
            能力:{' '}
            {grant.allowed_capabilities.length === 0
              ? '全部'
              : grant.allowed_capabilities.join(', ')}
          </div>
          <div className="mt-2">
            <GrantEntitlementsSummary teamId={grant.team_id} grantId={grant.id} />
          </div>
        </div>
      ))}
    </div>
  )
}
