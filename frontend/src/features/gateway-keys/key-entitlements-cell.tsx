import type { EntitlementPlan } from '@/api/gateway'
import { Badge } from '@/components/ui/badge'

export function KeyEntitlementsCell({
  activePlans,
  isLoading,
}: Readonly<{
  activePlans: EntitlementPlan[]
  isLoading: boolean
}>): React.JSX.Element {
  if (isLoading) return <span className="text-muted-foreground">加载中…</span>
  if (activePlans.length === 0) return <span className="text-muted-foreground">未配置</span>
  return (
    <div className="flex flex-wrap gap-1">
      {activePlans.slice(0, 2).map((plan) => (
        <Badge key={plan.id} variant="secondary" className="max-w-40 truncate">
          {plan.label}
        </Badge>
      ))}
      {activePlans.length > 2 ? <Badge variant="outline">+{activePlans.length - 2}</Badge> : null}
    </div>
  )
}
