/**
 * 配额概览 KPI 卡片：展示配额全局状态快照。
 */

import type { QuotaRule } from '@/api/gateway/quota-rules'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'

import {
  computeQuotaRuleUsageRatio,
  LAYER_LABELS,
  parseQuotaNumeric,
  quotaUsageHasMetrics,
} from './quota-rule-utils'

interface QuotaOverviewCardsProps {
  rules: QuotaRule[]
  isLoading?: boolean
  mode?: 'admin' | 'member'
}

function KpiCard({
  title,
  value,
  sub,
  variant = 'default',
  isLoading,
}: {
  title: string
  value: string
  sub?: string
  variant?: 'default' | 'warning' | 'danger'
  isLoading?: boolean
}): React.JSX.Element {
  const variantClass =
    variant === 'danger'
      ? 'text-destructive'
      : variant === 'warning'
        ? 'text-amber-600'
        : 'text-foreground'

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-xs font-medium text-muted-foreground">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className={cn('text-2xl font-semibold tabular-nums', variantClass)}>
          {isLoading ? '—' : value}
        </div>
        {sub ? <p className="mt-1 text-xs text-muted-foreground">{sub}</p> : null}
      </CardContent>
    </Card>
  )
}

export function QuotaOverviewCards({
  rules,
  isLoading,
  mode,
}: QuotaOverviewCardsProps): React.JSX.Element {
  // 按层级统计
  const layerCounts = { platform: 0, upstream: 0, downstream: 0 }
  let alertCount = 0
  let dangerCount = 0
  let totalUsd = 0
  let totalTokens = 0
  let totalRequests = 0
  let nearResetCount = 0
  const now = Date.now()
  const resetThreshold = 24 * 60 * 60 * 1000 // 24h

  for (const rule of rules) {
    layerCounts[rule.key.layer]++

    if (rule.usage && quotaUsageHasMetrics(rule.usage)) {
      totalUsd += parseQuotaNumeric(rule.usage.current_usd)
      totalTokens += parseQuotaNumeric(rule.usage.current_tokens)
      totalRequests += parseQuotaNumeric(rule.usage.current_requests)

      const { ratio } = computeQuotaRuleUsageRatio(rule)
      if (ratio >= 1) dangerCount++
      else if (ratio >= 0.8) alertCount++

      if (rule.usage.reset_at) {
        const resetTime = new Date(rule.usage.reset_at).getTime()
        if (resetTime > now && resetTime - now < resetThreshold) {
          nearResetCount++
        }
      }
      if (rule.usage.budget_reset_at) {
        const resetTime = new Date(rule.usage.budget_reset_at).getTime()
        if (resetTime > now && resetTime - now < resetThreshold) {
          nearResetCount++
        }
      }
    }
  }

  const totalCount = rules.length

  // P21: 成员模式简化为个人视角
  if (mode === 'member') {
    return (
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <KpiCard title="我的配额数" value={String(totalCount)} isLoading={isLoading} />
        <KpiCard
          title="本月已用"
          value={`$${parseQuotaNumeric(totalUsd).toFixed(2)}`}
          sub={`${totalTokens.toLocaleString()} Token`}
          isLoading={isLoading}
        />
        <KpiCard
          title="即将重置"
          value={String(nearResetCount)}
          sub={nearResetCount > 0 ? '24h 内重置' : undefined}
          variant={nearResetCount > 0 ? 'warning' : 'default'}
          isLoading={isLoading}
        />
      </div>
    )
  }

  const layerSub = `${LAYER_LABELS.platform} ${String(layerCounts.platform)} · ${LAYER_LABELS.upstream} ${String(layerCounts.upstream)} · ${LAYER_LABELS.downstream} ${String(layerCounts.downstream)}`
  const alertSub = dangerCount > 0 ? `其中 ${String(dangerCount)} 条已超限` : undefined

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <KpiCard
        title="配额规则总数"
        value={String(totalCount)}
        sub={layerSub}
        isLoading={isLoading}
      />
      <KpiCard
        title="告警配额"
        value={String(alertCount + dangerCount)}
        sub={alertSub}
        variant={dangerCount > 0 ? 'danger' : alertCount > 0 ? 'warning' : 'default'}
        isLoading={isLoading}
      />
      <KpiCard
        title="本月累计用量"
        value={`$${parseQuotaNumeric(totalUsd).toFixed(2)}`}
        sub={`${totalTokens.toLocaleString()} Token · ${totalRequests.toLocaleString()} 请求`}
        isLoading={isLoading}
      />
      <KpiCard
        title="即将重置"
        value={String(nearResetCount)}
        sub={nearResetCount > 0 ? '24h 内重置' : undefined}
        variant={nearResetCount > 0 ? 'warning' : 'default'}
        isLoading={isLoading}
      />
    </div>
  )
}
