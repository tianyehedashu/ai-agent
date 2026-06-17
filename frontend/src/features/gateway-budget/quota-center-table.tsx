/**
 * 配额中心表格：可调列宽、调用名/上游分列、排序、批量选择。
 */

import { memo, useMemo, useState } from 'react'

import { Link } from 'react-router-dom'

import type { QuotaRule } from '@/api/gateway/quota-rules'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { QuotaCenterResizableHeader } from '@/features/gateway-budget/quota-center-resizable-header'
import { useQuotaCenterColumnWidths } from '@/features/gateway-budget/use-quota-center-column-widths'
import { ArrowDown, ArrowUp, CircleDollarSign, Loader2, Pencil, Trash2 } from '@/lib/lucide-icons'
import { cn } from '@/lib/utils'

import {
  computeQuotaRuleUsageRatio,
  formatQuotaRuleInvokeNameLabel,
  formatQuotaRulePeriod,
  formatQuotaRulePeriodWindow,
  formatQuotaRuleUpstreamNameLabel,
  LAYER_LABELS,
  quotaUsageHasMetrics,
  LAYER_ORDER,
  quotaRuleRowId,
  resolveQuotaRuleModelDetailHref,
  resolveQuotaRulePlanManagementLink,
  resolveQuotaRuleCredentialLabel,
  resolveQuotaRuleSubjectLabel,
  type QuotaRuleLabelContext,
} from './quota-rule-utils'
import { QuotaUsageAdjustDialog } from './quota-usage-adjust-dialog'
import { isQuotaRuleUsageAdjustable } from './use-quota-usage-adjust'

import type { QuotaCenterMode } from './use-quota-center'

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
  teamId: string
  mode: QuotaCenterMode
  labelContext: QuotaRuleLabelContext
  onSelect: (rule: QuotaRule) => void
  onDelete: (rule: QuotaRule) => void
  onEdit?: (rule: QuotaRule) => void
  onBatchDelete?: (rules: QuotaRule[]) => void
}

type SortKey = 'layer' | 'subject' | 'invokeName' | 'upstream' | 'period' | 'usage' | 'limit'
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
    case 'invokeName':
      return formatQuotaRuleInvokeNameLabel(rule, ctx)
    case 'upstream':
      return formatQuotaRuleUpstreamNameLabel(rule, ctx)
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

const GRID_CELL = 'min-w-0 px-3 py-2 text-xs'

const SortHeader = memo(function SortHeader({
  label,
  sortKey,
  columnKey,
  currentSort,
  onSort,
  startResize,
  resetColumn,
  className,
}: {
  label: string
  sortKey: SortKey
  columnKey: Parameters<typeof QuotaCenterResizableHeader>[0]['columnKey']
  currentSort: SortState | null
  onSort: (key: SortKey) => void
  startResize: (
    key: Parameters<typeof QuotaCenterResizableHeader>[0]['columnKey'],
    clientX: number
  ) => void
  resetColumn: (key: Parameters<typeof QuotaCenterResizableHeader>[0]['columnKey']) => void
  className?: string
}) {
  const active = currentSort?.key === sortKey
  return (
    <QuotaCenterResizableHeader
      columnKey={columnKey}
      className={cn('cursor-pointer font-medium', className)}
      startResize={startResize}
      resetColumn={resetColumn}
    >
      <button
        type="button"
        className="inline-flex w-full items-center gap-1 text-left"
        onClick={() => {
          onSort(sortKey)
        }}
      >
        {label}
        {active ? (
          currentSort.dir === 'asc' ? (
            <ArrowUp className="h-3 w-3 shrink-0" />
          ) : (
            <ArrowDown className="h-3 w-3 shrink-0" />
          )
        ) : null}
      </button>
    </QuotaCenterResizableHeader>
  )
})

interface QuotaCenterTableRowProps {
  rule: QuotaRule
  gridTemplateColumns: string
  isSelected: boolean
  isChecked: boolean
  formDisabled: boolean
  labelContext: QuotaRuleLabelContext
  onSelect: (rule: QuotaRule) => void
  onToggleCheck: (rule: QuotaRule, checked: boolean) => void
  onEdit: (rule: QuotaRule) => void
  onDelete: (rule: QuotaRule) => void
  onAdjustUsage: (rule: QuotaRule) => void
}

const QuotaCenterTableRow = memo(function QuotaCenterTableRow({
  rule,
  gridTemplateColumns,
  isSelected,
  isChecked,
  formDisabled,
  labelContext,
  onSelect,
  onToggleCheck,
  onEdit,
  onDelete,
  onAdjustUsage,
}: QuotaCenterTableRowProps): React.JSX.Element {
  const { ratio, barColor } = computeQuotaRuleUsageRatio(rule)
  const limitUsd = rule.limits.limit_usd
  const limitTok = rule.limits.limit_tokens
  const usage = rule.usage
  const canEdit =
    rule.source_ref.budget_id !== null ||
    (rule.key.layer === 'upstream' && rule.source_ref.plan_id !== null)
  const canDelete = rule.source_ref.budget_id !== null
  const isPlanRule = rule.source_ref.budget_id === null
  const planLayer =
    rule.key.layer === 'upstream'
      ? ('upstream' as const)
      : rule.key.layer === 'downstream'
        ? ('downstream' as const)
        : null

  const invokeLabel = formatQuotaRuleInvokeNameLabel(rule, labelContext)
  const upstreamLabel = formatQuotaRuleUpstreamNameLabel(rule, labelContext)
  const modelDetailHref = resolveQuotaRuleModelDetailHref(rule, labelContext)

  return (
    <div
      role="row"
      className={cn(
        'grid cursor-pointer border-b last:border-0 hover:bg-muted/20',
        isSelected && 'bg-primary/5',
        !rule.is_active && 'opacity-60'
      )}
      style={{ gridTemplateColumns }}
      onClick={() => {
        onSelect(rule)
      }}
    >
      <div
        className={cn(GRID_CELL, 'flex items-center')}
        role="cell"
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
      </div>
      <div className={GRID_CELL} role="cell">
        {LAYER_LABELS[rule.key.layer]}
      </div>
      <div
        className={cn(GRID_CELL, 'truncate')}
        role="cell"
        title={resolveQuotaRuleSubjectLabel(rule, labelContext)}
      >
        {resolveQuotaRuleSubjectLabel(rule, labelContext)}
      </div>
      <div
        className={cn(GRID_CELL, 'truncate')}
        role="cell"
        title={resolveQuotaRuleCredentialLabel(rule, labelContext)}
      >
        {resolveQuotaRuleCredentialLabel(rule, labelContext)}
      </div>
      <div className={cn(GRID_CELL, 'truncate font-medium')} role="cell" title={invokeLabel}>
        {invokeLabel}
      </div>
      <div
        className={cn(GRID_CELL, 'truncate font-mono text-muted-foreground')}
        role="cell"
        title={upstreamLabel}
      >
        {upstreamLabel}
      </div>
      <div className={GRID_CELL} role="cell">
        <div>{formatQuotaRulePeriod(rule)}</div>
        {formatQuotaRulePeriodWindow(rule) ? (
          <div className="mt-0.5 text-[10px] text-muted-foreground">
            {formatQuotaRulePeriodWindow(rule)}
          </div>
        ) : null}
      </div>
      <div className={cn(GRID_CELL, 'tabular-nums')} role="cell">
        {usage && quotaUsageHasMetrics(usage) ? (
          <>
            USD {Number.parseFloat(String(usage.current_usd)).toFixed(4)} /{' '}
            {limitUsd !== null ? `$${Number.parseFloat(String(limitUsd)).toFixed(2)}` : '∞'}
            <br />
            Token {usage.current_tokens} / {limitTok ?? '∞'}
          </>
        ) : (
          <span className="text-muted-foreground">—</span>
        )}
      </div>
      <div className={GRID_CELL} role="cell">
        {usage && quotaUsageHasMetrics(usage) ? (
          <div className="flex items-center gap-2">
            <div className="h-2 w-full min-w-[4rem] overflow-hidden rounded bg-muted">
              <div
                className={`h-full ${barColor}`}
                style={{
                  width: `${Math.min(100, Math.max(0, ratio * 100)).toFixed(1)}%`,
                }}
              />
            </div>
            <span className="shrink-0 text-xs tabular-nums">{(ratio * 100).toFixed(1)}%</span>
          </div>
        ) : (
          <span className="text-muted-foreground">—</span>
        )}
      </div>
      <div className={GRID_CELL} role="cell">
        {rule.plan_label ? (
          <span className="inline-flex items-center rounded-md bg-blue-50 px-1.5 py-0.5 text-xs font-medium text-blue-700 dark:bg-blue-900/30 dark:text-blue-300">
            {rule.plan_label}
          </span>
        ) : (
          <span className="text-muted-foreground">自定义</span>
        )}
      </div>
      <div
        className={cn(GRID_CELL, 'flex items-center')}
        role="cell"
        onClick={(e) => {
          e.stopPropagation()
        }}
      >
        <div className="flex flex-wrap items-center gap-1">
          {canEdit ? (
            <Button
              size="icon"
              variant="ghost"
              className="h-7 w-7"
              disabled={formDisabled}
              onClick={() => {
                onEdit(rule)
              }}
              title={modelDetailHref ? '去模型详情管理配额' : '编辑配额'}
            >
              <Pencil className="h-3.5 w-3.5 text-muted-foreground" />
            </Button>
          ) : null}
          {!formDisabled && isQuotaRuleUsageAdjustable(rule) ? (
            <Button
              size="icon"
              variant="ghost"
              className="h-7 w-7"
              onClick={() => {
                onAdjustUsage(rule)
              }}
              title="设置本周期已用额度"
            >
              <CircleDollarSign className="h-3.5 w-3.5 text-muted-foreground" />
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
      </div>
    </div>
  )
})

export function QuotaCenterTable({
  items,
  isLoading,
  selectedId,
  formDisabled,
  teamId,
  mode,
  labelContext,
  onSelect,
  onDelete,
  onEdit,
  onBatchDelete,
}: QuotaCenterTableProps): React.JSX.Element {
  const [sort, setSort] = useState<SortState | null>({ key: 'usage', dir: 'desc' })
  const [checkedIds, setCheckedIds] = useState<Set<string>>(new Set())
  const [adjustRule, setAdjustRule] = useState<QuotaRule | null>(null)
  const { gridTemplateColumns, tableMinWidth, startResize, resetColumn } =
    useQuotaCenterColumnWidths()

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

  const headerClass = 'grid border-b bg-muted/30 px-3 py-2 text-xs uppercase text-muted-foreground'

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
        <div className="overflow-x-auto">
          <div style={{ minWidth: tableMinWidth }}>
            <div className={headerClass} style={{ gridTemplateColumns }} role="row">
              <div className="flex items-center px-0" role="columnheader">
                <Checkbox
                  checked={allChecked ? true : someChecked ? 'indeterminate' : false}
                  onCheckedChange={toggleAll}
                  aria-label="全选"
                />
              </div>
              <SortHeader
                label="层级"
                sortKey="layer"
                columnKey="layer"
                currentSort={sort}
                onSort={handleSort}
                startResize={startResize}
                resetColumn={resetColumn}
              />
              <SortHeader
                label="主体"
                sortKey="subject"
                columnKey="subject"
                currentSort={sort}
                onSort={handleSort}
                startResize={startResize}
                resetColumn={resetColumn}
              />
              <QuotaCenterResizableHeader
                columnKey="credential"
                className="font-medium"
                startResize={startResize}
                resetColumn={resetColumn}
              >
                凭据
              </QuotaCenterResizableHeader>
              <SortHeader
                label="调用名"
                sortKey="invokeName"
                columnKey="invokeName"
                currentSort={sort}
                onSort={handleSort}
                startResize={startResize}
                resetColumn={resetColumn}
              />
              <SortHeader
                label="上游"
                sortKey="upstream"
                columnKey="upstream"
                currentSort={sort}
                onSort={handleSort}
                startResize={startResize}
                resetColumn={resetColumn}
              />
              <SortHeader
                label="周期"
                sortKey="period"
                columnKey="period"
                currentSort={sort}
                onSort={handleSort}
                startResize={startResize}
                resetColumn={resetColumn}
              />
              <SortHeader
                label="已用 / 限额"
                sortKey="limit"
                columnKey="usage"
                currentSort={sort}
                onSort={handleSort}
                startResize={startResize}
                resetColumn={resetColumn}
              />
              <SortHeader
                label="使用率"
                sortKey="usage"
                columnKey="usageRatio"
                currentSort={sort}
                onSort={handleSort}
                startResize={startResize}
                resetColumn={resetColumn}
              />
              <QuotaCenterResizableHeader
                columnKey="source"
                className="font-medium"
                startResize={startResize}
                resetColumn={resetColumn}
              >
                来源
              </QuotaCenterResizableHeader>
              <div className="min-w-0 font-medium" role="columnheader">
                操作
              </div>
            </div>

            {isLoading ? (
              <div className="px-4 py-8 text-center text-sm text-muted-foreground">
                <Loader2 className="mx-auto mb-2 h-4 w-4 animate-spin" />
                加载中…
              </div>
            ) : null}
            {!isLoading && items.length === 0 ? (
              <div className="px-4 py-8 text-center text-sm text-muted-foreground">
                暂无配额规则
              </div>
            ) : null}
            {sortedItems.map((rule) => {
              const rowId = quotaRuleRowId(rule)
              return (
                <QuotaCenterTableRow
                  key={rowId}
                  rule={rule}
                  gridTemplateColumns={gridTemplateColumns}
                  isSelected={selectedId === rowId}
                  isChecked={checkedIds.has(rowId)}
                  formDisabled={formDisabled}
                  labelContext={labelContext}
                  onSelect={onSelect}
                  onToggleCheck={toggleRow}
                  onEdit={onEdit ?? (() => {})}
                  onDelete={onDelete}
                  onAdjustUsage={setAdjustRule}
                />
              )
            })}
          </div>
        </div>
      </CardContent>
      <QuotaUsageAdjustDialog
        teamId={teamId}
        mode={mode}
        rule={adjustRule}
        open={adjustRule !== null}
        onOpenChange={(open) => {
          if (!open) setAdjustRule(null)
        }}
      />
    </Card>
  )
}
