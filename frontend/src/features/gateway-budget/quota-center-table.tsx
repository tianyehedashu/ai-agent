import { memo } from 'react'

import type { QuotaRule } from '@/api/gateway/quota-rules'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Loader2, Trash2 } from '@/lib/lucide-icons'
import { cn } from '@/lib/utils'

import {
  computeQuotaRuleUsageRatio,
  formatQuotaRulePeriod,
  LAYER_LABELS,
  quotaRuleRowId,
  resolveQuotaRuleCredentialLabel,
  resolveQuotaRuleSubjectLabel,
  type QuotaRuleLabelContext,
} from './quota-rule-utils'

export interface QuotaCenterTableProps {
  items: QuotaRule[]
  isLoading: boolean
  selectedId: string | null
  formDisabled: boolean
  labelContext: QuotaRuleLabelContext
  onSelect: (rule: QuotaRule) => void
  onDelete: (rule: QuotaRule) => void
}

interface QuotaCenterTableRowProps {
  rule: QuotaRule
  isSelected: boolean
  formDisabled: boolean
  labelContext: QuotaRuleLabelContext
  onSelect: (rule: QuotaRule) => void
  onDelete: (rule: QuotaRule) => void
}

const QuotaCenterTableRow = memo(function QuotaCenterTableRow({
  rule,
  isSelected,
  formDisabled,
  labelContext,
  onSelect,
  onDelete,
}: QuotaCenterTableRowProps): React.JSX.Element {
  const { ratio, barColor } = computeQuotaRuleUsageRatio(rule)
  const limitUsd = rule.limits.limit_usd
  const limitTok = rule.limits.limit_tokens
  const usage = rule.usage
  const canDelete = rule.source_ref.budget_id !== null

  return (
    <tr
      className={cn(
        'cursor-pointer border-b last:border-0 hover:bg-muted/20',
        isSelected && 'bg-primary/5',
        !rule.is_active && 'opacity-60'
      )}
      onClick={() => {
        onSelect(rule)
      }}
    >
      <td className="px-4 py-2 text-xs">{LAYER_LABELS[rule.key.layer]}</td>
      <td className="px-4 py-2 text-xs">{resolveQuotaRuleSubjectLabel(rule, labelContext)}</td>
      <td className="max-w-[120px] truncate px-4 py-2 text-xs">
        {resolveQuotaRuleCredentialLabel(rule, labelContext)}
      </td>
      <td className="max-w-[140px] truncate px-4 py-2 text-xs">
        {rule.key.model_name ?? '（全模型）'}
      </td>
      <td className="px-4 py-2 text-xs">{formatQuotaRulePeriod(rule)}</td>
      <td className="px-4 py-2 text-xs tabular-nums">
        {usage ? (
          <>
            USD {usage.current_usd.toFixed(4)} /{' '}
            {limitUsd !== null ? `$${limitUsd.toFixed(2)}` : '∞'}
            <br />
            Token {usage.current_tokens} / {limitTok ?? '∞'}
          </>
        ) : (
          <span className="text-muted-foreground">—</span>
        )}
      </td>
      <td className="px-4 py-2">
        {usage ? (
          <div className="flex items-center gap-2">
            <div className="h-2 w-24 overflow-hidden rounded bg-muted">
              <div
                className={`h-full ${barColor}`}
                style={{
                  width: `${Math.min(100, Math.max(0, ratio * 100)).toFixed(1)}%`,
                }}
              />
            </div>
            <span className="text-xs tabular-nums">{(ratio * 100).toFixed(1)}%</span>
          </div>
        ) : (
          <span className="text-xs text-muted-foreground">—</span>
        )}
      </td>
      <td className="px-4 py-2">
        {canDelete ? (
          <Button
            size="icon"
            variant="ghost"
            className="h-7 w-7"
            disabled={formDisabled}
            onClick={(e) => {
              e.stopPropagation()
              onDelete(rule)
            }}
          >
            <Trash2 className="h-3.5 w-3.5 text-destructive" />
          </Button>
        ) : null}
      </td>
    </tr>
  )
})

export function QuotaCenterTable({
  items,
  isLoading,
  selectedId,
  formDisabled,
  labelContext,
  onSelect,
  onDelete,
}: QuotaCenterTableProps): React.JSX.Element {
  return (
    <Card>
      <CardContent className="p-0">
        <table className="w-full text-sm">
          <thead className="border-b bg-muted/30 text-xs uppercase text-muted-foreground">
            <tr>
              <th className="px-4 py-2 text-left font-medium">层级</th>
              <th className="px-4 py-2 text-left font-medium">主体</th>
              <th className="px-4 py-2 text-left font-medium">凭据</th>
              <th className="px-4 py-2 text-left font-medium">模型</th>
              <th className="px-4 py-2 text-left font-medium">周期</th>
              <th className="px-4 py-2 text-left font-medium">已用 / 限额</th>
              <th className="px-4 py-2 text-left font-medium">使用率</th>
              <th className="px-4 py-2 text-left font-medium" />
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={8} className="px-4 py-8 text-center text-muted-foreground">
                  <Loader2 className="mx-auto mb-2 h-4 w-4 animate-spin" />
                  加载中…
                </td>
              </tr>
            ) : null}
            {!isLoading && items.length === 0 ? (
              <tr>
                <td colSpan={8} className="px-4 py-8 text-center text-muted-foreground">
                  暂无配额规则
                </td>
              </tr>
            ) : null}
            {items.map((rule) => {
              const rowId = quotaRuleRowId(rule)
              return (
                <QuotaCenterTableRow
                  key={rowId}
                  rule={rule}
                  isSelected={selectedId === rowId}
                  formDisabled={formDisabled}
                  labelContext={labelContext}
                  onSelect={onSelect}
                  onDelete={onDelete}
                />
              )
            })}
          </tbody>
        </table>
      </CardContent>
    </Card>
  )
}
