import type React from 'react'

import type { UsageStatisticsBreakdownResponse } from '@/api/gateway/stats'
import { cn } from '@/lib/utils'

export interface UsageStatsBreakdownListProps {
  data: UsageStatisticsBreakdownResponse | undefined
  loading?: boolean
  className?: string
}

export function UsageStatsBreakdownList({
  data,
  loading = false,
  className,
}: Readonly<UsageStatsBreakdownListProps>): React.JSX.Element {
  if (loading) {
    return <span className={cn('text-xs text-muted-foreground', className)}>…</span>
  }

  if (!data || data.items.length === 0) {
    return <span className={cn('text-muted-foreground', className)}>—</span>
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
