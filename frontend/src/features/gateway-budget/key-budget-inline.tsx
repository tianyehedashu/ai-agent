import type { GatewayBudget } from '@/api/gateway/budgets'
import { Badge } from '@/components/ui/badge'

import { computeBudgetUsageMetrics, formatBudgetPeriod } from './budget-progress-utils'

export function KeyBudgetInline({ budgets }: { budgets: GatewayBudget[] }): React.JSX.Element {
  if (budgets.length === 0) {
    return <span className="text-muted-foreground">—</span>
  }
  return (
    <div className="flex flex-wrap gap-1">
      {budgets.map((b) => {
        const { ratio } = computeBudgetUsageMetrics(b)
        const variant = ratio >= 1 ? 'destructive' : ratio >= 0.9 ? 'secondary' : 'outline'
        return (
          <Badge key={b.id} variant={variant} className="text-[10px] font-normal tabular-nums">
            {formatBudgetPeriod(b.period)} {(ratio * 100).toFixed(0)}%
          </Badge>
        )
      })}
    </div>
  )
}
