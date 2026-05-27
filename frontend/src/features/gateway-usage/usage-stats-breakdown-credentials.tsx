import type React from 'react'

import type { UsageStatisticsBreakdownResponse } from '@/api/gateway/stats'
import { cn } from '@/lib/utils'

import { credentialBreakdownFooterHints } from './usage-stats-breakdown-hints'

export interface UsageStatsBreakdownCredentialsProps {
  data: UsageStatisticsBreakdownResponse | undefined
  loading?: boolean
  requestedTopN?: number
  className?: string
}

/** 凭据列：展示父行下全部已返回的凭据 slice（无 Top 分档序号）。 */
export function UsageStatsBreakdownCredentials({
  data,
  loading = false,
  requestedTopN = 32,
  className,
}: Readonly<UsageStatsBreakdownCredentialsProps>): React.JSX.Element {
  if (loading) {
    return <span className={cn('text-xs text-muted-foreground', className)}>…</span>
  }

  if (!data || data.items.length === 0) {
    return <span className={cn('text-muted-foreground', className)}>—</span>
  }

  const footerHints = credentialBreakdownFooterHints(data, requestedTopN)

  return (
    <div className={cn('min-w-0', className)}>
      <ul className="max-h-28 space-y-1 overflow-y-auto text-xs">
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
      {footerHints.map((hint) => (
        <p key={hint} className="mt-1 text-[10px] text-muted-foreground">
          {hint}
        </p>
      ))}
      {data.items.length > 1 && footerHints.length === 0 ? (
        <p className="mt-0.5 text-[10px] tabular-nums text-muted-foreground">
          共 {data.items.length} 个凭据
        </p>
      ) : null}
    </div>
  )
}
