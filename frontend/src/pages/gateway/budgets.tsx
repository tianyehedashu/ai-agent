/**
 * AI Gateway · 预算配额（Admin 专页）
 */

import { useEffect } from 'react'

import { Navigate } from 'react-router-dom'

import { BudgetAdminWorkspace } from '@/features/gateway-budget/budget-admin-workspace'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useGatewayTeamId } from '@/hooks/use-gateway-team-id'

function teamOverviewHref(teamId: string): string {
  return `/gateway/teams/${encodeURIComponent(teamId)}/overview`
}

export default function GatewayBudgetsPage(): React.JSX.Element {
  const teamId = useGatewayTeamId()
  const { isAdmin } = useGatewayPermission()

  useEffect(() => {
    document.title = '预算配额 · AI Gateway'
  }, [])

  if (!isAdmin) {
    return <Navigate to={teamOverviewHref(teamId)} replace />
  }

  return <BudgetAdminWorkspace />
}
