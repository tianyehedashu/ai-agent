/**
 * API Key Gateway grant 下游套餐展示
 */

import type React from 'react'

import { useQuery } from '@tanstack/react-query'

import { entitlementsApi, type EntitlementPlan } from '@/api/gateway/entitlements'
import { Badge } from '@/components/ui/badge'

const GRANT_ENTITLEMENTS_STALE_MS = 60_000

interface GrantEntitlementsSummaryProps {
  teamId: string
  grantId: string
}

export function GrantEntitlementsSummary({
  teamId,
  grantId,
}: GrantEntitlementsSummaryProps): React.ReactElement {
  const { data: plans = [], isLoading } = useQuery({
    queryKey: ['gateway', 'grant-entitlements', teamId, grantId],
    queryFn: () => entitlementsApi.listGrantEntitlements(teamId, grantId),
    enabled: Boolean(teamId && grantId),
    staleTime: GRANT_ENTITLEMENTS_STALE_MS,
  })

  const active = plans.filter((plan: EntitlementPlan) => plan.is_active)

  if (isLoading) {
    return <span className="text-xs text-muted-foreground">套餐加载中…</span>
  }

  if (active.length === 0) {
    return <span className="text-xs text-muted-foreground">未配置下游套餐</span>
  }

  return (
    <div className="flex flex-wrap gap-1">
      {active.slice(0, 3).map((plan) => (
        <Badge key={plan.id} variant="secondary" className="text-xs">
          {plan.label}
        </Badge>
      ))}
      {active.length > 3 ? (
        <Badge variant="outline" className="text-xs">
          +{active.length - 3}
        </Badge>
      ) : null}
    </div>
  )
}
