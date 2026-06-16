import type { QuotaRule } from '@/api/gateway/quota-rules'
import {
  computeQuotaRuleUsageRatio,
  describeUpstreamQuotaRuleScope,
  formatQuotaRulePeriod,
} from '@/features/gateway-budget/quota-rule-utils'
import { formatQuotaTokens } from '@/features/gateway-budget/quota-token-display'
import { Cloud, Shield } from '@/lib/lucide-icons'
import { cn } from '@/lib/utils'

interface ModelDetailQuotaRuleRowProps {
  rule: QuotaRule
  layer: 'platform' | 'upstream'
  credentialLabel?: string | null
  /** 当前模型 upstream endpoint，用于区分「本 endpoint / 整凭据」 */
  upstreamModelId?: string
  actions?: React.ReactNode
}

export function ModelDetailQuotaRuleRow({
  rule,
  layer,
  credentialLabel,
  upstreamModelId,
  actions,
}: ModelDetailQuotaRuleRowProps): React.JSX.Element {
  const { ratio, barColor } = computeQuotaRuleUsageRatio(rule)
  const limitUsd = rule.limits.limit_usd
  const limitTok = rule.limits.limit_tokens
  const usage = rule.usage
  const isPlatform = layer === 'platform'
  const upstreamScope = !isPlatform ? describeUpstreamQuotaRuleScope(rule, upstreamModelId) : null

  const subtitleParts = [formatQuotaRulePeriod(rule)]
  if (!isPlatform && credentialLabel) subtitleParts.push(credentialLabel)
  if (upstreamScope) subtitleParts.push(upstreamScope)

  const primaryMetric =
    limitUsd !== null
      ? `$${parseFloat(String(limitUsd)).toFixed(2)}`
      : limitTok !== null
        ? formatQuotaTokens(limitTok)
        : '未设上限'

  return (
    <div
      className={cn(
        'rounded-md border p-3',
        isPlatform
          ? 'border-sky-500/20 bg-sky-500/[0.04]'
          : 'border-amber-500/25 bg-amber-500/[0.06]'
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="flex min-w-0 items-start gap-2">
          <div
            className={cn(
              'mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md',
              isPlatform
                ? 'bg-sky-500/10 text-sky-700 dark:text-sky-300'
                : 'bg-amber-500/15 text-amber-700 dark:text-amber-300'
            )}
          >
            {isPlatform ? <Shield className="h-3.5 w-3.5" /> : <Cloud className="h-3.5 w-3.5" />}
          </div>
          <div className="min-w-0 space-y-0.5">
            <p className="text-sm font-medium">{isPlatform ? '网关侧' : '厂商侧'}</p>
            <p className="text-xs text-muted-foreground">{subtitleParts.join(' · ')}</p>
          </div>
        </div>
        {actions}
      </div>

      {usage ? (
        <div className="mt-3 space-y-2">
          <div className="grid gap-2 text-xs tabular-nums sm:grid-cols-2">
            <div className="rounded bg-background/60 px-2 py-1.5">
              <p className="text-[10px] uppercase tracking-wide text-muted-foreground">费用</p>
              <p className="mt-0.5 font-medium">
                ${parseFloat(String(usage.current_usd)).toFixed(2)} /{' '}
                {limitUsd !== null ? `$${parseFloat(String(limitUsd)).toFixed(2)}` : '∞'}
              </p>
            </div>
            <div className="rounded bg-background/60 px-2 py-1.5">
              <p className="text-[10px] uppercase tracking-wide text-muted-foreground">Token</p>
              <p className="mt-0.5 font-medium">
                {formatQuotaTokens(usage.current_tokens)} / {formatQuotaTokens(limitTok)}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
              <div
                className={`h-full ${barColor}`}
                style={{ width: `${Math.min(100, Math.max(0, ratio * 100)).toFixed(1)}%` }}
              />
            </div>
            <span className="text-[11px] tabular-nums text-muted-foreground">
              {(ratio * 100).toFixed(0)}%
            </span>
          </div>
        </div>
      ) : (
        <p className="mt-2 text-xs text-muted-foreground">上限 {primaryMetric}</p>
      )}
    </div>
  )
}
