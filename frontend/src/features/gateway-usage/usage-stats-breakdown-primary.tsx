import type React from 'react'

import type { UsageStatisticsBreakdownResponse } from '@/api/gateway/stats'
import { cn } from '@/lib/utils'

export interface UsageStatsBreakdownPrimaryProps {
  data: UsageStatisticsBreakdownResponse | undefined
  loading?: boolean
  className?: string
}

/** 模型列：仅展示 Top1 主项（单行）。 */
export function UsageStatsBreakdownPrimary({
  data,
  loading = false,
  className,
}: Readonly<UsageStatsBreakdownPrimaryProps>): React.JSX.Element {
  if (loading) {
    return <span className={cn('text-xs text-muted-foreground', className)}>…</span>
  }

  const slice = data?.items[0]
  if (!slice) {
    return <span className={cn('text-muted-foreground', className)}>—</span>
  }

  return (
    <div className={cn('min-w-0 text-xs', className)}>
      <div className="truncate font-medium" title={slice.label}>
        {slice.label}
      </div>
      <div className="tabular-nums text-muted-foreground">
        {(slice.share * 100).toFixed(0)}% · {slice.requests.toLocaleString()} 次
      </div>
    </div>
  )
}
