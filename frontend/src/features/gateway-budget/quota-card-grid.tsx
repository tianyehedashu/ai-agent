/**
 * 配额规则卡片网格视图：按模型/人员/凭据分组展示配额卡片。
 */

import { memo, useMemo, useState } from 'react'

import type { QuotaRule } from '@/api/gateway/quota-rules'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { LayoutGrid, List } from '@/lib/lucide-icons'

import { QuotaCardItem } from './quota-card-item'
import {
  computeQuotaRuleUsageRatio,
  quotaRuleRowId,
  type QuotaRuleLabelContext,
} from './quota-rule-utils'

export type QuotaViewMode = 'table' | 'card'
export type QuotaGroupBy = 'none' | 'model' | 'subject' | 'credential' | 'layer'

interface QuotaCardGridProps {
  items: QuotaRule[]
  isLoading: boolean
  selectedId: string | null
  labelContext: QuotaRuleLabelContext
  viewMode: QuotaViewMode
  onViewModeChange: (mode: QuotaViewMode) => void
  onSelect: (rule: QuotaRule) => void
  onEdit?: (rule: QuotaRule) => void
  onAddFromRule?: (rule: QuotaRule) => void
  canAddFromRule?: (rule: QuotaRule) => boolean
  onDelete?: (rule: QuotaRule) => void
  onCreate?: () => void
  formDisabled?: boolean
}

function groupRulesBy(
  rules: QuotaRule[],
  groupBy: QuotaGroupBy,
  labelContext: QuotaRuleLabelContext
): Map<string, QuotaRule[]> {
  const groups = new Map<string, QuotaRule[]>()
  if (groupBy === 'none') {
    groups.set('全部', rules)
    return groups
  }

  for (const rule of rules) {
    let key: string
    switch (groupBy) {
      case 'model':
        key = rule.key.model_name ?? '全模型'
        break
      case 'subject': {
        const subject =
          rule.key.target_kind === 'tenant'
            ? '全团队'
            : rule.key.target_kind === 'system'
              ? '系统'
              : rule.key.user_id
                ? (labelContext.memberLabels.get(rule.key.user_id) ?? '成员')
                : rule.key.access_id
                  ? (labelContext.keyLabels.get(rule.key.access_id) ?? 'Key')
                  : '—'
        key = subject
        break
      }
      case 'credential': {
        key = rule.key.credential_id
          ? (labelContext.credentialLabels.get(rule.key.credential_id) ?? '凭据')
          : '—'
        break
      }
      case 'layer':
        key =
          rule.key.layer === 'platform' ? '平台' : rule.key.layer === 'upstream' ? '上游' : '下游'
        break
      default:
        key = '全部'
    }
    const existing = groups.get(key) ?? []
    existing.push(rule)
    groups.set(key, existing)
  }
  return groups
}

const GroupHeader = memo(function GroupHeader({
  title,
  count,
  avgRatio,
}: {
  title: string
  count: number
  avgRatio: number
}) {
  return (
    <div className="flex items-center gap-3 py-2">
      <h3 className="text-sm font-semibold">{title}</h3>
      <span className="text-xs text-muted-foreground">{count} 条</span>
      {avgRatio > 0 ? (
        <span
          className={
            avgRatio >= 0.9
              ? 'text-xs text-destructive'
              : avgRatio >= 0.6
                ? 'text-xs text-amber-600'
                : 'text-xs text-emerald-600'
          }
        >
          平均 {(avgRatio * 100).toFixed(0)}%
        </span>
      ) : null}
    </div>
  )
})

export function QuotaCardGrid({
  items,
  isLoading,
  selectedId,
  labelContext,
  viewMode,
  onViewModeChange,
  onSelect,
  onEdit,
  onAddFromRule,
  canAddFromRule,
  onDelete,
  onCreate,
  formDisabled = false,
}: QuotaCardGridProps): React.JSX.Element {
  const [groupBy, setGroupBy] = useState<QuotaGroupBy>('none')
  const [sortBy, setSortBy] = useState<'usage_desc' | 'usage_asc' | 'name'>('usage_desc')

  const sortedItems = useMemo(() => {
    const arr = [...items]
    if (sortBy === 'usage_desc') {
      arr.sort((a, b) => {
        const ra = computeQuotaRuleUsageRatio(a).ratio
        const rb = computeQuotaRuleUsageRatio(b).ratio
        return rb - ra
      })
    } else if (sortBy === 'usage_asc') {
      arr.sort((a, b) => {
        const ra = computeQuotaRuleUsageRatio(a).ratio
        const rb = computeQuotaRuleUsageRatio(b).ratio
        return ra - rb
      })
    } else {
      arr.sort((a, b) => {
        const na = a.key.model_name ?? ''
        const nb = b.key.model_name ?? ''
        return na.localeCompare(nb)
      })
    }
    return arr
  }, [items, sortBy])

  const groups = useMemo(
    () => groupRulesBy(sortedItems, groupBy, labelContext),
    [sortedItems, groupBy, labelContext]
  )

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="h-40 animate-pulse rounded-lg bg-muted" />
        ))}
      </div>
    )
  }

  if (items.length === 0) {
    return (
      <div className="flex flex-col items-center gap-3 py-12 text-center text-sm text-muted-foreground">
        <span>暂无配额规则</span>
        {!formDisabled && onCreate ? (
          <Button size="sm" onClick={onCreate}>
            新增配额
          </Button>
        ) : null}
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-1 rounded-md border bg-background p-0.5">
          <Button
            size="sm"
            variant={viewMode === 'table' ? 'default' : 'ghost'}
            className="h-7 gap-1 px-2 text-xs"
            onClick={() => {
              onViewModeChange('table')
            }}
          >
            <List className="h-3.5 w-3.5" />
            表格
          </Button>
          <Button
            size="sm"
            variant={viewMode === 'card' ? 'default' : 'ghost'}
            className="h-7 gap-1 px-2 text-xs"
            onClick={() => {
              onViewModeChange('card')
            }}
          >
            <LayoutGrid className="h-3.5 w-3.5" />
            卡片
          </Button>
        </div>

        <div className="flex items-center gap-2">
          <Label className="text-xs text-muted-foreground">分组</Label>
          <Select
            value={groupBy}
            onValueChange={(v) => {
              setGroupBy(v as QuotaGroupBy)
            }}
          >
            <SelectTrigger className="h-7 w-28 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="none">不分组</SelectItem>
              <SelectItem value="model">按模型</SelectItem>
              <SelectItem value="subject">按主体</SelectItem>
              <SelectItem value="credential">按凭据</SelectItem>
              <SelectItem value="layer">按层级</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="flex items-center gap-2">
          <Label className="text-xs text-muted-foreground">排序</Label>
          <Select
            value={sortBy}
            onValueChange={(v) => {
              setSortBy(v as typeof sortBy)
            }}
          >
            <SelectTrigger className="h-7 w-36 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="usage_desc">使用率 ↓</SelectItem>
              <SelectItem value="usage_asc">使用率 ↑</SelectItem>
              <SelectItem value="name">模型名</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {Array.from(groups.entries()).map(([groupName, groupRules]) => {
        const avgRatio =
          groupRules.reduce((sum, r) => sum + computeQuotaRuleUsageRatio(r).ratio, 0) /
          (groupRules.length || 1)

        return (
          <div key={groupName}>
            {groupBy !== 'none' && (
              <GroupHeader title={groupName} count={groupRules.length} avgRatio={avgRatio} />
            )}
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {groupRules.map((rule) => {
                const rowId = quotaRuleRowId(rule)
                return (
                  <QuotaCardItem
                    key={rowId}
                    rule={rule}
                    labelContext={labelContext}
                    isSelected={selectedId === rowId}
                    onClick={onSelect}
                    onEdit={onEdit}
                    onAddFromRule={onAddFromRule}
                    canAddFromRule={canAddFromRule}
                    onDelete={onDelete}
                    formDisabled={formDisabled}
                  />
                )
              })}
            </div>
          </div>
        )
      })}
    </div>
  )
}
