import type React from 'react'

import type { QuotaRule } from '@/api/gateway/quota-rules'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import {
  computeQuotaRuleUsageRatio,
  formatQuotaRulePeriod,
  LAYER_LABELS,
} from '@/features/gateway-budget/quota-rule-utils'
import { formatCompact } from '@/lib/number'

function quotaUsageText(rule: QuotaRule): string {
  const usage = rule.usage
  if (rule.limits.limit_usd !== null) {
    return `$${(usage?.current_usd ?? 0).toFixed(2)} / $${rule.limits.limit_usd.toFixed(2)}`
  }
  if (rule.limits.limit_tokens !== null) {
    return `${formatCompact(usage?.current_tokens ?? 0)} / ${formatCompact(rule.limits.limit_tokens)} tok`
  }
  if (rule.limits.limit_requests !== null) {
    return `${(usage?.current_requests ?? 0).toLocaleString()} / ${rule.limits.limit_requests.toLocaleString()} 次`
  }
  if (rule.limits.limit_images !== null) {
    return `${(usage?.current_images ?? 0).toLocaleString()} / ${rule.limits.limit_images.toLocaleString()} 图`
  }
  return '∞'
}

/** 调用统计行内：展示对应配额的「已用/上限」与使用率迷你条。 */
export function UsageStatsQuotaCell({
  rule,
}: {
  rule: QuotaRule | null | undefined
}): React.JSX.Element {
  if (!rule) {
    return <span className="text-xs text-muted-foreground">—</span>
  }
  const { ratio, barColor } = computeQuotaRuleUsageRatio(rule)
  const pct = Math.min(100, Math.max(0, ratio * 100))
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <div className="ml-auto flex w-[120px] cursor-help flex-col items-end gap-1">
          <span className="text-[11px] tabular-nums">{quotaUsageText(rule)}</span>
          <div className="h-1.5 w-full overflow-hidden rounded bg-muted">
            <div className={`h-full ${barColor}`} style={{ width: `${pct.toFixed(1)}%` }} />
          </div>
        </div>
      </TooltipTrigger>
      <TooltipContent side="top">
        <div className="space-y-0.5 text-xs">
          <div>
            {LAYER_LABELS[rule.key.layer]} · {formatQuotaRulePeriod(rule)}配额
          </div>
          <div className="tabular-nums">使用率 {(ratio * 100).toFixed(1)}%</div>
        </div>
      </TooltipContent>
    </Tooltip>
  )
}
