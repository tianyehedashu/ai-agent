/**
 * 配额中心表格：支持列排序、批量选择、行删除。
 */

import { memo, useMemo, useState } from 'react'

import { Link } from 'react-router-dom'

import type { QuotaRule } from '@/api/gateway/quota-rules'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { ArrowDown, ArrowUp, Loader2, Pencil, Trash2 } from '@/lib/lucide-icons'
import { cn } from '@/lib/utils'

import {
  computeQuotaRuleUsageRatio,
  formatQuotaRulePeriod,
  LAYER_LABELS,
  LAYER_ORDER,
  quotaRuleRowId,
  resolveQuotaRulePlanManagementLink,
  resolveQuotaRuleCredentialLabel,
  resolveQuotaRuleSubjectLabel,
  type QuotaRuleLabelContext,
} from './quota-rule-utils'

/** 计划类 upstream/downstream 规则的管理页跳转 */
function PlanRuleManagementHint({
  rule,
  labelContext,
}: {
  rule: QuotaRule
  labelContext: QuotaRuleLabelContext
}): React.JSX.Element | null {
  if (
    rule.key.layer === 'upstream' &&
    rule.key.model_name &&
    labelContext.planRuleModelLookupLoading
  ) {
    return <span className="text-xs text-muted-foreground">加载模型…</span>
  }
  const link = resolveQuotaRulePlanManagementLink(rule, labelContext)
  if (!link) return null
  return (
    <Link
      to={link.href}
      className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
      onClick={(e) => {
        e.stopPropagation()
      }}
    >
      {link.label}
    </Link>
  )
}

export interface QuotaCenterTableProps {
  items: QuotaRule[]
  isLoading: boolean
  selectedId: string | null
  formDisabled: boolean
  labelContext: QuotaRuleLabelContext
  onSelect: (rule: QuotaRule) => void
  onDelete: (rule: QuotaRule) => void
  onEdit?: (rule: QuotaRule) => void
  onBatchDelete?: (rules: QuotaRule[]) => void
}

type SortKey = 'layer' | 'subject' | 'model' | 'period' | 'usage' | 'limit'
type SortDir = 'asc' | 'desc'

interface SortState {
  key: SortKey
  dir: SortDir
}

function getSortValue(rule: QuotaRule, key: SortKey, ctx: QuotaRuleLabelContext): string | number {
  switch (key) {
    case 'layer':
      return LAYER_ORDER[rule.key.layer]
    case 'subject':
      return resolveQuotaRuleSubjectLabel(rule, ctx)
    case 'model':
      return rule.key.model_name ?? ''
    case 'period':
      return formatQuotaRulePeriod(rule)
    case 'usage': {
      const { ratio } = computeQuotaRuleUsageRatio(rule)
      return ratio
    }
    case 'limit': {
      const lu = rule.limits.limit_usd
      const lt = rule.limits.limit_tokens
      if (lu !== null) return lu
      if (lt !== null) return lt
      return 0
    }
    default:
      return 0
  }
}

function sortRules(rules: QuotaRule[], sort: SortState, ctx: QuotaRuleLabelContext): QuotaRule[] {
  const arr = [...rules]
  arr.sort((a, b) => {
    const va = getSortValue(a, sort.key, ctx)
    const vb = getSortValue(b, sort.key, ctx)
    if (typeof va === 'string' && typeof vb === 'string') {
      return sort.dir === 'asc' ? va.localeCompare(vb) : vb.localeCompare(va)
    }
    const na = typeof va === 'number' ? va : 0
    const nb = typeof vb === 'number' ? vb : 0
    return sort.dir === 'asc' ? na - nb : nb - na
  })
  return arr
}

const SortHeader = memo(function SortHeader({
  label,
  sortKey,
  currentSort,
  onSort,
}: {
  label: string
  sortKey: SortKey
  currentSort: SortState | null
  onSort: (key: SortKey) => void
}) {
  const active = currentSort?.key === sortKey
  return (
    <th
      className="cursor-pointer select-none px-4 py-2 text-left font-medium"
      onClick={() => {
        onSort(sortKey)
      }}
    >
      <span className="inline-flex items-center gap-1">
        {label}
        {active ? (
          currentSort.dir === 'asc' ? (
            <ArrowUp className="h-3 w-3" />
          ) : (
            <ArrowDown className="h-3 w-3" />
          )
        ) : null}
      </span>
    </th>
  )
})

interface QuotaCenterTableRowProps {
  rule: QuotaRule
  isSelected: boolean
  isChecked: boolean
  formDisabled: boolean
  labelContext: QuotaRuleLabelContext
  onSelect: (rule: QuotaRule) => void
  onToggleCheck: (rule: QuotaRule, checked: boolean) => void
  onEdit: (rule: QuotaRule) => void
  onDelete: (rule: QuotaRule) => void
}

const QuotaCenterTableRow = memo(function QuotaCenterTableRow({
  rule,
  isSelected,
  isChecked,
  formDisabled,
  labelContext,
  onSelect,
  onToggleCheck,
  onEdit,
  onDelete,
}: QuotaCenterTableRowProps): React.JSX.Element {
  const { ratio, barColor } = computeQuotaRuleUsageRatio(rule)
  const limitUsd = rule.limits.limit_usd
  const limitTok = rule.limits.limit_tokens
  const usage = rule.usage
  const canDelete = rule.source_ref.budget_id !== null
  const isPlanRule = rule.source_ref.budget_id === null
  const planLayer =
    rule.key.layer === 'upstream'
      ? ('upstream' as const)
      : rule.key.layer === 'downstream'
        ? ('downstream' as const)
        : null

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
      <td
        className="px-4 py-2"
        onClick={(e) => {
          e.stopPropagation()
        }}
      >
        <Checkbox
          checked={isChecked}
          onCheckedChange={(v) => {
            onToggleCheck(rule, v === true)
          }}
          aria-label="选择此行"
        />
      </td>
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
            USD {Number.parseFloat(String(usage.current_usd)).toFixed(4)} /{' '}
            {limitUsd !== null ? `$${Number.parseFloat(String(limitUsd)).toFixed(2)}` : '∞'}
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
      {/* P12: 来源列 */}
      <td className="px-4 py-2">
        {rule.plan_label ? (
          <span className="inline-flex items-center rounded-md bg-blue-50 px-1.5 py-0.5 text-xs font-medium text-blue-700 dark:bg-blue-900/30 dark:text-blue-300">
            {rule.plan_label}
          </span>
        ) : (
          <span className="text-xs text-muted-foreground">自定义</span>
        )}
      </td>
      <td
        className="px-4 py-2"
        onClick={(e) => {
          e.stopPropagation()
        }}
      >
        <div className="flex items-center gap-1">
          {rule.source_ref.budget_id !== null ? (
            <Button
              size="icon"
              variant="ghost"
              className="h-7 w-7"
              disabled={formDisabled}
              onClick={() => {
                onEdit(rule)
              }}
              title="编辑配额"
            >
              <Pencil className="h-3.5 w-3.5 text-muted-foreground" />
            </Button>
          ) : null}
          {canDelete ? (
            <Button
              size="icon"
              variant="ghost"
              className="h-7 w-7"
              disabled={formDisabled}
              onClick={() => {
                onDelete(rule)
              }}
              title="删除配额"
            >
              <Trash2 className="h-3.5 w-3.5 text-destructive" />
            </Button>
          ) : null}
          {isPlanRule && planLayer ? (
            <PlanRuleManagementHint rule={rule} labelContext={labelContext} />
          ) : null}
        </div>
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
  onEdit,
  onBatchDelete,
}: QuotaCenterTableProps): React.JSX.Element {
  const [sort, setSort] = useState<SortState | null>({ key: 'usage', dir: 'desc' })
  const [checkedIds, setCheckedIds] = useState<Set<string>>(new Set())

  const sortedItems = useMemo(() => {
    if (!sort) return items
    return sortRules(items, sort, labelContext)
  }, [items, sort, labelContext])

  const handleSort = (key: SortKey): void => {
    setSort((prev) => {
      if (prev?.key === key) {
        return { key, dir: prev.dir === 'asc' ? 'desc' : 'asc' }
      }
      return { key, dir: 'desc' }
    })
  }

  const allChecked =
    sortedItems.length > 0 && sortedItems.every((r) => checkedIds.has(quotaRuleRowId(r)))
  const someChecked = sortedItems.some((r) => checkedIds.has(quotaRuleRowId(r)))

  const toggleAll = (): void => {
    if (allChecked) {
      setCheckedIds((prev) => {
        const next = new Set(prev)
        for (const r of sortedItems) next.delete(quotaRuleRowId(r))
        return next
      })
    } else {
      setCheckedIds((prev) => {
        const next = new Set(prev)
        for (const r of sortedItems) next.add(quotaRuleRowId(r))
        return next
      })
    }
  }

  const toggleRow = (rule: QuotaRule, checked: boolean): void => {
    const id = quotaRuleRowId(rule)
    setCheckedIds((prev) => {
      const next = new Set(prev)
      if (checked) next.add(id)
      else next.delete(id)
      return next
    })
  }

  const checkedRules = useMemo(
    () => sortedItems.filter((r) => checkedIds.has(quotaRuleRowId(r))),
    [sortedItems, checkedIds]
  )

  const handleBatchDelete = (): void => {
    if (checkedRules.length === 0) return
    onBatchDelete?.(checkedRules)
    setCheckedIds(new Set())
  }

  return (
    <Card>
      <CardContent className="p-0">
        {someChecked ? (
          <div className="flex items-center gap-3 border-b bg-muted/20 px-4 py-2">
            <span className="text-xs text-muted-foreground">已选 {checkedRules.length} 条</span>
            <Button
              size="sm"
              variant="destructive"
              className="h-7 text-xs"
              disabled={formDisabled}
              onClick={handleBatchDelete}
            >
              <Trash2 className="mr-1 h-3 w-3" />
              批量删除
            </Button>
          </div>
        ) : null}
        <table className="w-full text-sm">
          <thead className="border-b bg-muted/30 text-xs uppercase text-muted-foreground">
            <tr>
              <th className="px-4 py-2 text-left">
                <Checkbox
                  checked={allChecked ? true : someChecked ? 'indeterminate' : false}
                  onCheckedChange={toggleAll}
                  aria-label="全选"
                />
              </th>
              <SortHeader label="层级" sortKey="layer" currentSort={sort} onSort={handleSort} />
              <SortHeader label="主体" sortKey="subject" currentSort={sort} onSort={handleSort} />
              <th className="px-4 py-2 text-left font-medium">凭据</th>
              <SortHeader label="模型" sortKey="model" currentSort={sort} onSort={handleSort} />
              <SortHeader label="周期" sortKey="period" currentSort={sort} onSort={handleSort} />
              <SortHeader
                label="已用 / 限额"
                sortKey="limit"
                currentSort={sort}
                onSort={handleSort}
              />
              <SortHeader label="使用率" sortKey="usage" currentSort={sort} onSort={handleSort} />
              <th className="px-4 py-2 text-left font-medium">来源</th>
              <th className="px-4 py-2 text-left font-medium" />
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={10} className="px-4 py-8 text-center text-muted-foreground">
                  <Loader2 className="mx-auto mb-2 h-4 w-4 animate-spin" />
                  加载中…
                </td>
              </tr>
            ) : null}
            {!isLoading && items.length === 0 ? (
              <tr>
                <td colSpan={10} className="px-4 py-8 text-center text-muted-foreground">
                  暂无配额规则
                </td>
              </tr>
            ) : null}
            {sortedItems.map((rule) => {
              const rowId = quotaRuleRowId(rule)
              return (
                <QuotaCenterTableRow
                  key={rowId}
                  rule={rule}
                  isSelected={selectedId === rowId}
                  isChecked={checkedIds.has(rowId)}
                  formDisabled={formDisabled}
                  labelContext={labelContext}
                  onSelect={onSelect}
                  onToggleCheck={toggleRow}
                  onEdit={onEdit ?? (() => {})}
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
