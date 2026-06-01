import type { GatewayBudget } from '@/api/gateway/budgets'
import { Badge } from '@/components/ui/badge'

import { computeBudgetUsageMetrics, formatBudgetPeriod } from './budget-progress-utils'

export function PersonalCredentialBudgetBadges({
  budgets,
}: {
  budgets: GatewayBudget[]
}): React.JSX.Element {
  if (budgets.length === 0) {
    return <span className="text-xs text-muted-foreground">暂无平台预算</span>
  }

  return (
    <div className="space-y-1">
      <div className="flex flex-wrap gap-1">
        {budgets.map((b) => {
          const { ratio } = computeBudgetUsageMetrics(b)
          const variant = ratio >= 1 ? 'destructive' : ratio >= 0.9 ? 'secondary' : 'outline'
          const modelLabel = b.model_name ?? '全模型'
          return (
            <Badge key={b.id} variant={variant} className="text-[10px] font-normal tabular-nums">
              {formatBudgetPeriod(b.period)} · {modelLabel} · {(ratio * 100).toFixed(0)}%
            </Badge>
          )
        })}
      </div>
      <p className="text-[10px] text-muted-foreground">
        个人 BYOK 凭据不受平台配额强制（仅作展示/软约束）。
      </p>
    </div>
  )
}
