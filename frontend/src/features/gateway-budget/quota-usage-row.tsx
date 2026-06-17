import type { QuotaRule } from '@/api/gateway/quota-rules'
import { cn } from '@/lib/utils'

import {
  computeQuotaRuleUsageRatio,
  formatQuotaRulePeriod,
  formatQuotaRulePeriodWindow,
  LAYER_LABELS,
  quotaUsageHasMetrics,
  resolveQuotaRuleModelLabel,
  type QuotaRuleLabelContext,
} from './quota-rule-utils'
import { formatQuotaTokens } from './quota-token-display'

export interface QuotaUsageRowProps {
  rule: QuotaRule
  labelContext?: QuotaRuleLabelContext
  actions?: React.ReactNode
}

const LAYER_ROW_STYLE = {
  platform: 'border-border/60 bg-muted/20',
  upstream: 'border-amber-500/25 bg-amber-500/5',
  downstream: 'border-border/60 bg-muted/20',
} as const

export function QuotaUsageRow({
  rule,
  labelContext,
  actions,
}: QuotaUsageRowProps): React.JSX.Element {
  const { ratio, barColor } = computeQuotaRuleUsageRatio(rule)
  const limitUsd = rule.limits.limit_usd
  const limitTok = rule.limits.limit_tokens
  const usage = rule.usage
  const layer = rule.key.layer
  const rowStyle = LAYER_ROW_STYLE[layer]

  return (
    <div className={cn('space-y-2 rounded-md border p-3', rowStyle)}>
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
        <span className="font-medium">
          {LAYER_LABELS[layer]} · {formatQuotaRulePeriod(rule)}
        </span>
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-muted-foreground">
            {resolveQuotaRuleModelLabel(rule, labelContext)}
          </span>
          {actions}
        </div>
      </div>
      {usage && quotaUsageHasMetrics(usage) ? (
        <>
          <div className="space-y-0.5 text-xs tabular-nums">
            <div>
              USD {parseFloat(String(usage.current_usd)).toFixed(4)} /{' '}
              {limitUsd !== null ? `$${parseFloat(String(limitUsd)).toFixed(2)}` : '∞'}
            </div>
            <div>
              Token {formatQuotaTokens(usage.current_tokens)} / {formatQuotaTokens(limitTok)}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className="h-2 flex-1 overflow-hidden rounded bg-muted">
              <div
                className={`h-full ${barColor}`}
                style={{ width: `${Math.min(100, Math.max(0, ratio * 100)).toFixed(1)}%` }}
              />
            </div>
            <span className="text-xs tabular-nums">{(ratio * 100).toFixed(1)}%</span>
          </div>
        </>
      ) : (
        <div className="text-xs tabular-nums text-muted-foreground">
          限额 USD {limitUsd ?? '∞'} · Token {formatQuotaTokens(limitTok)}
        </div>
      )}
      {formatQuotaRulePeriodWindow(rule) ? (
        <p className="text-[11px] text-muted-foreground">{formatQuotaRulePeriodWindow(rule)}</p>
      ) : null}
    </div>
  )
}
