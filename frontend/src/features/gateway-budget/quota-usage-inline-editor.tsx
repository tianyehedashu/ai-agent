import { useEffect, useMemo, useState } from 'react'

import type { QuotaRule, QuotaRuleUsage } from '@/api/gateway/quota-rules'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  computeQuotaRuleUsageRatio,
  isSlidingRollingWindow,
  quotaUsageHasMetrics,
} from '@/features/gateway-budget/quota-rule-utils'
import { formatQuotaTokens } from '@/features/gateway-budget/quota-token-display'
import {
  buildQuotaUsageAdjustmentBody,
  useQuotaUsageAdjust,
} from '@/features/gateway-budget/use-quota-usage-adjust'
import { Loader2 } from '@/lib/lucide-icons'

import type { QuotaCenterMode } from './use-quota-center'

interface QuotaUsageInlineEditorProps {
  rule: QuotaRule
  teamId: string
  mode: QuotaCenterMode
  canEdit: boolean
  limitUsd: number | string | null
  limitTok: number | null
}

function usageFieldStrings(rule: QuotaRule): { usd: string; tokens: string; requests: string } {
  const body = buildQuotaUsageAdjustmentBody(rule)
  return {
    usd: String(body.current_usd ?? 0),
    tokens: String(body.current_tokens ?? 0),
    requests: String(body.current_requests ?? 0),
  }
}

export function QuotaUsageInlineEditor({
  rule,
  teamId,
  mode,
  canEdit,
  limitUsd,
  limitTok,
}: QuotaUsageInlineEditorProps): React.JSX.Element {
  const baseline = useMemo(() => usageFieldStrings(rule), [rule])
  const [usd, setUsd] = useState(baseline.usd)
  const [tokens, setTokens] = useState(baseline.tokens)
  const [requests, setRequests] = useState(baseline.requests)

  const { adjustUsage, resetWindow, pending } = useQuotaUsageAdjust({ teamId, mode })

  useEffect(() => {
    setUsd(baseline.usd)
    setTokens(baseline.tokens)
    setRequests(baseline.requests)
  }, [baseline.requests, baseline.tokens, baseline.usd])

  const dirty = usd !== baseline.usd || tokens !== baseline.tokens || requests !== baseline.requests

  const previewRule = useMemo((): QuotaRule => {
    const usage: QuotaRuleUsage = {
      current_usd: Number.parseFloat(usd) || 0,
      current_tokens: Number.parseInt(tokens, 10) || 0,
      current_requests: Number.parseInt(requests, 10) || 0,
      window_start: rule.usage?.window_start ?? null,
      reset_at: rule.usage?.reset_at ?? null,
      budget_reset_at: rule.usage?.budget_reset_at ?? null,
    }
    return { ...rule, usage }
  }, [requests, rule, tokens, usd])

  // 滚动窗口用量由请求日志实时统计，桶写入不反映到展示，故不提供手工校正/清零。
  const isRolling = isSlidingRollingWindow(rule)
  const effectiveCanEdit = canEdit && !isRolling

  const { ratio, barColor } = computeQuotaRuleUsageRatio(previewRule)
  const hasLimits = limitUsd !== null || limitTok !== null
  const showProgress =
    hasLimits && (effectiveCanEdit || (rule.usage !== null && quotaUsageHasMetrics(rule.usage)))

  const limitUsdLabel =
    limitUsd !== null ? `$${Number.parseFloat(String(limitUsd)).toFixed(2)}` : '∞'
  const limitTokLabel = formatQuotaTokens(limitTok)

  const handleSave = (): void => {
    const ref = rule.source_ref
    adjustUsage({
      layer: rule.key.layer,
      budget_id: ref.budget_id,
      plan_id: ref.plan_id,
      quota_id: ref.quota_id,
      mode: 'set',
      current_usd: Number.parseFloat(usd) || 0,
      current_tokens: Number.parseInt(tokens, 10) || 0,
      current_requests: Number.parseInt(requests, 10) || 0,
    })
  }

  const handleReset = (): void => {
    if (!window.confirm('确定将本周期已用额度清零？')) return
    resetWindow(rule)
  }

  if (!effectiveCanEdit) {
    const usage = rule.usage
    if (!usage || !quotaUsageHasMetrics(usage)) {
      return <p className="mt-2 text-xs text-muted-foreground">暂无本周期用量数据</p>
    }
    return (
      <div className="mt-3 space-y-2">
        <div className="grid gap-2 text-xs tabular-nums sm:grid-cols-2">
          <div className="rounded bg-background/60 px-2 py-1.5">
            <p className="text-[10px] uppercase tracking-wide text-muted-foreground">已用费用</p>
            <p className="mt-0.5 font-medium">
              ${Number.parseFloat(String(usage.current_usd)).toFixed(2)} / {limitUsdLabel}
            </p>
          </div>
          <div className="rounded bg-background/60 px-2 py-1.5">
            <p className="text-[10px] uppercase tracking-wide text-muted-foreground">已用 Token</p>
            <p className="mt-0.5 font-medium">
              {formatQuotaTokens(usage.current_tokens)} / {limitTokLabel}
            </p>
          </div>
        </div>
        {showProgress ? <UsageProgressBar ratio={ratio} barColor={barColor} /> : null}
        {canEdit && isRolling ? (
          <p className="text-[11px] text-muted-foreground">
            滚动窗口用量按请求日志实时统计，不支持手工校正 / 清零；如需可改为每日 / 每月固定周期。
          </p>
        ) : null}
      </div>
    )
  }

  return (
    <div className="mt-3 space-y-2">
      <div className="grid gap-2 text-xs sm:grid-cols-2">
        <label className="space-y-1 rounded bg-background/60 px-2 py-1.5">
          <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
            已用费用 (USD)
          </span>
          <div className="flex items-center gap-1.5 tabular-nums">
            <Input
              inputMode="decimal"
              className="h-7 flex-1 px-2 text-xs"
              value={usd}
              disabled={pending}
              onChange={(e) => {
                setUsd(e.target.value)
              }}
            />
            <span className="shrink-0 text-muted-foreground">/ {limitUsdLabel}</span>
          </div>
        </label>
        <label className="space-y-1 rounded bg-background/60 px-2 py-1.5">
          <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
            已用 Token
          </span>
          <div className="flex items-center gap-1.5 tabular-nums">
            <Input
              inputMode="numeric"
              className="h-7 flex-1 px-2 text-xs"
              value={tokens}
              disabled={pending}
              onChange={(e) => {
                setTokens(e.target.value)
              }}
            />
            <span className="shrink-0 text-muted-foreground">/ {limitTokLabel}</span>
          </div>
        </label>
      </div>

      {showProgress ? <UsageProgressBar ratio={ratio} barColor={barColor} /> : null}

      <div className="flex flex-wrap items-center justify-end gap-1.5">
        <Button
          type="button"
          size="sm"
          variant="ghost"
          className="h-7 text-xs"
          disabled={pending}
          onClick={handleReset}
        >
          清零本周期
        </Button>
        <Button
          type="button"
          size="sm"
          className="h-7 text-xs"
          disabled={!dirty || pending}
          onClick={handleSave}
        >
          {pending ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : null}
          保存
        </Button>
      </div>
    </div>
  )
}

function UsageProgressBar({
  ratio,
  barColor,
}: {
  ratio: number
  barColor: string
}): React.JSX.Element {
  return (
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
  )
}
