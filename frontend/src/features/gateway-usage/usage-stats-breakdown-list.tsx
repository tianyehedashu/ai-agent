import type React from 'react'

import type { UsageStatisticsBreakdownResponse } from '@/api/gateway/stats'
import { cn } from '@/lib/utils'

export type UsageStatsBreakdownListVariant = 'compact' | 'sheet'

export interface UsageStatsBreakdownListProps {
  data: UsageStatisticsBreakdownResponse | undefined
  loading?: boolean
  variant?: UsageStatsBreakdownListVariant
  className?: string
}

/** 分布详情等场景：展示 breakdown 列表（非表格凭据/模型专用列）。 */
export function UsageStatsBreakdownList({
  data,
  loading = false,
  variant = 'compact',
  className,
}: Readonly<UsageStatsBreakdownListProps>): React.JSX.Element {
  if (loading) {
    return (
      <p className={cn('text-sm text-muted-foreground', className)}>
        {variant === 'sheet' ? '加载中…' : '…'}
      </p>
    )
  }

  if (!data || data.items.length === 0) {
    return (
      <p
        className={cn(
          variant === 'sheet' ? 'text-sm text-muted-foreground' : 'text-muted-foreground',
          className
        )}
      >
        {variant === 'sheet' ? '暂无数据' : '—'}
      </p>
    )
  }

  if (variant === 'sheet') {
    return (
      <ul className={cn('space-y-2 text-sm', className)}>
        {data.items.map((slice) => (
          <li
            key={slice.group_key}
            className="flex items-center justify-between gap-2 border-b border-dashed pb-2 last:border-0"
          >
            <span className="min-w-0 truncate font-medium" title={slice.label}>
              {slice.label}
            </span>
            <span className="shrink-0 tabular-nums text-muted-foreground">
              {slice.requests.toLocaleString()}（{(slice.share * 100).toFixed(1)}%）
            </span>
          </li>
        ))}
      </ul>
    )
  }

  return (
    <ul className={cn('space-y-1 text-xs', className)}>
      {data.items.map((slice) => (
        <li key={slice.group_key} className="min-w-0">
          <div className="flex items-baseline justify-between gap-2">
            <span className="truncate font-medium" title={slice.label}>
              {slice.label}
            </span>
            <span className="shrink-0 tabular-nums text-muted-foreground">
              {(slice.share * 100).toFixed(0)}%
            </span>
          </div>
          <div className="text-[10px] tabular-nums text-muted-foreground">
            {slice.requests.toLocaleString()} 次
          </div>
        </li>
      ))}
    </ul>
  )
}
