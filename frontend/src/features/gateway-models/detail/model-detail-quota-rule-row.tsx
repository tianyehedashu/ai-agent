import type { QuotaRule } from '@/api/gateway/quota-rules'
import {
  formatQuotaRulePeriod,
  formatQuotaRulePeriodWindow,
} from '@/features/gateway-budget/quota-rule-utils'
import { formatQuotaTokens } from '@/features/gateway-budget/quota-token-display'
import { QuotaUsageInlineEditor } from '@/features/gateway-budget/quota-usage-inline-editor'
import type { QuotaCenterMode } from '@/features/gateway-budget/use-quota-center'
import { isQuotaRuleUsageAdjustable } from '@/features/gateway-budget/use-quota-usage-adjust'
import { Cloud, Shield } from '@/lib/lucide-icons'
import { cn } from '@/lib/utils'

interface ModelDetailQuotaRuleRowProps {
  rule: QuotaRule
  layer: 'platform' | 'upstream'
  teamId: string
  mode: QuotaCenterMode
  canAdjustUsage: boolean
  credentialLabel?: string | null
  /** 当前模型 upstream endpoint，用于区分「本 endpoint / 整凭据」 */
  upstreamModelId?: string
  gatewayAliasName?: string
  actions?: React.ReactNode
}

export function ModelDetailQuotaRuleRow({
  rule,
  layer,
  teamId,
  mode,
  canAdjustUsage,
  upstreamModelId,
  gatewayAliasName,
  actions,
}: ModelDetailQuotaRuleRowProps): React.JSX.Element {
  const limitUsd = rule.limits.limit_usd
  const limitTok = rule.limits.limit_tokens
  const limitReq = rule.limits.limit_requests
  const isPlatform = layer === 'platform'
  const canEditUsage = canAdjustUsage && isQuotaRuleUsageAdjustable(rule)

  const subtitleParts = [formatQuotaRulePeriod(rule)]
  if (gatewayAliasName) subtitleParts.push(`调用 ${gatewayAliasName}`)
  if (!isPlatform && upstreamModelId) subtitleParts.push(`上游 ${upstreamModelId}`)

  const primaryMetric =
    limitUsd !== null
      ? `$${Number.parseFloat(String(limitUsd)).toFixed(2)}`
      : limitTok !== null
        ? formatQuotaTokens(limitTok)
        : '未设上限'

  const periodWindow = formatQuotaRulePeriodWindow(rule)

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
            {periodWindow ? (
              <p className="text-[11px] text-muted-foreground">{periodWindow}</p>
            ) : null}
          </div>
        </div>
        {actions ? (
          <span className="inline-flex flex-wrap items-center gap-1">{actions}</span>
        ) : null}
      </div>

      {canEditUsage || rule.usage ? (
        <QuotaUsageInlineEditor
          rule={rule}
          teamId={teamId}
          mode={mode}
          canEdit={canEditUsage}
          limitUsd={limitUsd}
          limitTok={limitTok}
          limitReq={limitReq}
        />
      ) : (
        <p className="mt-2 text-xs text-muted-foreground">上限 {primaryMetric}</p>
      )}
    </div>
  )
}
