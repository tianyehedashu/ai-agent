/**
 * 配额规则卡片单项：展示主体、层级、模型、限额与使用率，支持编辑/删除操作。
 */

import { Link } from 'react-router-dom'

import type { QuotaRule } from '@/api/gateway/quota-rules'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { credentialsListHref } from '@/features/gateway-models/paths'
import { Pencil, Trash2 } from '@/lib/lucide-icons'
import { cn } from '@/lib/utils'

import {
  computeQuotaRuleUsageRatio,
  formatQuotaRulePeriod,
  LAYER_LABELS,
  parseQuotaNumeric,
  type QuotaRuleLabelContext,
} from './quota-rule-utils'

export interface QuotaCardItemProps {
  rule: QuotaRule
  labelContext: QuotaRuleLabelContext
  onClick?: (rule: QuotaRule) => void
  isSelected?: boolean
  onEdit?: (rule: QuotaRule) => void
  onDelete?: (rule: QuotaRule) => void
  formDisabled?: boolean
}

export function QuotaCardItem({
  rule,
  labelContext,
  onClick,
  isSelected,
  onEdit,
  onDelete,
  formDisabled = false,
}: QuotaCardItemProps): React.JSX.Element {
  const { ratio, barColor } = computeQuotaRuleUsageRatio(rule)
  const limitUsd = rule.limits.limit_usd
  const limitTok = rule.limits.limit_tokens
  const usage = rule.usage
  const canEdit = rule.source_ref.budget_id !== null
  const canDelete = rule.source_ref.budget_id !== null
  const isPlanRule = rule.source_ref.budget_id === null

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
          <div className="flex items-center gap-1">
            <Badge
              variant="secondary"
              className={cn('shrink-0 text-[10px]', layerColor[rule.key.layer])}
            >
              {LAYER_LABELS[rule.key.layer]}
            </Badge>
            {canEdit && onEdit ? (
              <Button
                size="icon"
                variant="ghost"
                className="h-6 w-6"
                disabled={formDisabled}
                onClick={(e) => {
                  e.stopPropagation()
                  onEdit(rule)
                }}
                title="编辑配额"
              >
                <Pencil className="h-3 w-3 text-muted-foreground" />
              </Button>
            ) : null}
            {canDelete && onDelete ? (
              <Button
                size="icon"
                variant="ghost"
                className="h-6 w-6"
                disabled={formDisabled}
                onClick={(e) => {
                  e.stopPropagation()
                  onDelete(rule)
                }}
                title="删除配额"
              >
                <Trash2 className="h-3 w-3 text-destructive" />
              </Button>
            ) : null}
          </div>
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
            <span>{usage ? parseQuotaNumeric(usage.current_usd).toFixed(2) : '—'}</span>
            <span className="text-muted-foreground">
              {' '}
              / {limitUsd !== null ? `$${parseQuotaNumeric(limitUsd).toFixed(2)}` : '∞'}
            </span>
          </div>
          <div>
            <span className="text-muted-foreground">Token</span>{' '}
            <span>{usage ? parseQuotaNumeric(usage.current_tokens).toLocaleString() : '—'}</span>
            <span className="text-muted-foreground">
              {' '}
              / {limitTok !== null ? parseQuotaNumeric(limitTok).toLocaleString() : '∞'}
            </span>
          </div>
        </div>
        {isPlanRule ? (
          <div className="flex items-center justify-between">
            <span className="inline-flex items-center rounded-md bg-blue-50 px-1.5 py-0.5 text-[11px] font-medium text-blue-700 dark:bg-blue-900/30 dark:text-blue-300">
              {rule.plan_label ?? '计划'}
            </span>
            <Link
              to={
                rule.key.layer === 'upstream'
                  ? credentialsListHref(rule.key.team_id, {
                      credentialId: rule.key.credential_id ?? undefined,
                    })
                  : `/gateway/virtual-keys${rule.key.access_id ? `?id=${rule.key.access_id}` : ''}`
              }
              className="text-[11px] text-primary hover:underline"
              onClick={(e) => {
                e.stopPropagation()
              }}
            >
              去{rule.key.layer === 'upstream' ? '凭据' : 'Key'}页管理
            </Link>
          </div>
        ) : (
          <div>
            <span className="text-[11px] text-muted-foreground">自定义</span>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
