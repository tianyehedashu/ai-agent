/**
 * AI Gateway · 配额中心
 *
 * 管理员：全团队配额管理；普通成员：「我的配额」自助查看与设置本人凭据限额。
 */

import { Suspense, useEffect } from 'react'

import { useGatewayPermission } from '@/hooks/use-gateway-permission'
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

export default function GatewayBudgetsPage(): React.JSX.Element {
  const { isAdmin } = useGatewayPermission()

  useEffect(() => {
    document.title = `${isAdmin ? '配额中心' : '我的配额'} · AI Gateway`
  }, [isAdmin])

  return (
    <Suspense fallback={adminWorkspaceFallback}>
      <QuotaCenterWorkspace />
    </Suspense>
  )
}
