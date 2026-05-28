/**
 * 配额规则卡片单项：展示主体、层级、模型、限额与使用率。
 */

import type { QuotaRule } from '@/api/gateway/quota-rules'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { cn } from '@/lib/utils'

import {
  computeQuotaRuleUsageRatio,
  formatQuotaRulePeriod,
  LAYER_LABELS,
  type QuotaRuleLabelContext,
} from './quota-rule-utils'

export interface QuotaCardItemProps {
  rule: QuotaRule
  labelContext: QuotaRuleLabelContext
  onClick?: (rule: QuotaRule) => void
  isSelected?: boolean
}

export function QuotaCardItem({
  rule,
  labelContext,
  onClick,
  isSelected,
}: QuotaCardItemProps): React.JSX.Element {
  const { ratio, barColor } = computeQuotaRuleUsageRatio(rule)
  const limitUsd = rule.limits.limit_usd
  const limitTok = rule.limits.limit_tokens
  const usage = rule.usage

  const layerColor: Record<string, string> = {
    platform: 'bg-blue-500/10 text-blue-600',
    upstream: 'bg-amber-500/10 text-amber-600',
    downstream: 'bg-emerald-500/10 text-emerald-600',
  }

  const subjectLabel =
    rule.key.target_kind === 'tenant'
      ? '全团队'
      : rule.key.target_kind === 'system'
        ? '系统'
        : rule.key.user_id
          ? (labelContext.memberLabels.get(rule.key.user_id) ?? '成员')
          : rule.key.access_id
            ? (labelContext.keyLabels.get(rule.key.access_id) ?? 'Key')
            : '—'

  return (
    <Card
      className={cn(
        'cursor-pointer transition-shadow hover:shadow-md',
        isSelected && 'ring-1 ring-primary'
      )}
      onClick={() => onClick?.(rule)}
    >
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <div className="truncate text-sm font-medium">{subjectLabel}</div>
            <div className="truncate text-xs text-muted-foreground">
              {rule.key.model_name ?? '全模型'}
            </div>
          </div>
          <Badge
            variant="secondary"
            className={cn('shrink-0 text-[10px]', layerColor[rule.key.layer])}
          >
            {LAYER_LABELS[rule.key.layer]}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-3 pt-0">
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>{formatQuotaRulePeriod(rule)}</span>
          <span className="tabular-nums">{(ratio * 100).toFixed(1)}%</span>
        </div>
        <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
          <div
            className={cn('h-full', barColor)}
            style={{ width: `${Math.min(100, ratio * 100).toFixed(1)}%` }}
          />
        </div>
        <div className="grid grid-cols-2 gap-2 text-xs tabular-nums">
          <div>
            <span className="text-muted-foreground">USD</span>{' '}
            <span>{usage ? usage.current_usd.toFixed(2) : '—'}</span>
            <span className="text-muted-foreground">
              {' '}
              / {limitUsd !== null ? `$${limitUsd.toFixed(2)}` : '∞'}
            </span>
          </div>
          <div>
            <span className="text-muted-foreground">Token</span>{' '}
            <span>{usage ? usage.current_tokens.toLocaleString() : '—'}</span>
            <span className="text-muted-foreground">
              {' '}
              / {limitTok !== null ? limitTok.toLocaleString() : '∞'}
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
