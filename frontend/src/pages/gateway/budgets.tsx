/**
 * AI Gateway · 预算配额（Admin 专页）
 */

import { Suspense, useEffect } from 'react'

import { Navigate } from 'react-router-dom'

import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useGatewayTeamId } from '@/hooks/use-gateway-team-id'
import { lazyWithReload } from '@/lib/lazy-with-reload'
import { Loader2 } from '@/lib/lucide-icons'

const QuotaCenterWorkspace = lazyWithReload(() =>
  import('@/features/gateway-budget/quota-center-workspace').then((m) => ({
    default: m.QuotaCenterWorkspace,
  }))
)

const adminWorkspaceFallback = (
  <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground">
    <Loader2 className="h-4 w-4 animate-spin" />
    加载配额中心…
  </div>
)

function teamOverviewHref(teamId: string): string {
  return `/gateway/teams/${encodeURIComponent(teamId)}/overview`
}

export default function GatewayBudgetsPage(): React.JSX.Element {
  const teamId = useGatewayTeamId()
  const { isAdmin } = useGatewayPermission()

  useEffect(() => {
    document.title = '配额中心 · AI Gateway'
  }, [])

  if (!isAdmin) {
    return <Navigate to={teamOverviewHref(teamId)} replace />
  }

  return (
    <Suspense fallback={adminWorkspaceFallback}>
      <QuotaCenterWorkspace />
    </Suspense>
  )
}
