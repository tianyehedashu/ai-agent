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

const BAR_COLORS = [
  'bg-blue-500',
  'bg-emerald-500',
  'bg-amber-500',
  'bg-rose-500',
  'bg-violet-500',
  'bg-cyan-500',
  'bg-orange-500',
  'bg-pink-500',
]

function BarSegment({
  color,
  width,
  label,
  share,
  requests,
}: Readonly<{
  color: string
  width: string
  label: string
  share: number
  requests: number
}>): React.JSX.Element {
  return (
    <div
      className={cn('h-full', color)}
      style={{ width }}
      title={`${label}: ${(share * 100).toFixed(0)}% · ${requests.toLocaleString()} 次`}
    />
  )
}

/** 凭据列：横向堆叠条 + Top1 标签，替代原先的行中列表。 */
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
  const top1 = data.items[0]

  return (
    <div className={cn('min-w-0', className)}>
      <div className="flex h-1.5 overflow-hidden rounded-full bg-muted">
        {data.items.map((slice, i) => {
          const width = `${Math.max(1, slice.share * 100).toFixed(1)}%`
          return (
            <BarSegment
              key={slice.group_key}
              color={BAR_COLORS[i % BAR_COLORS.length]}
              width={width}
              label={slice.label}
              share={slice.share}
              requests={slice.requests}
            />
          )
        })}
      </div>
      <div className="mt-1.5 flex items-center gap-1.5 text-xs">
        <span className="truncate font-medium" title={top1.label}>
          {top1.label}
        </span>
        <span className="shrink-0 tabular-nums text-muted-foreground">
          {(top1.share * 100).toFixed(0)}%
        </span>
        {data.items.length > 1 ? (
          <span className="shrink-0 text-[10px] text-muted-foreground">
            +{data.items.length - 1}
          </span>
        ) : null}
      </div>
      {footerHints.map((hint) => (
        <p key={hint} className="mt-0.5 text-[10px] text-muted-foreground">
          {hint}
        </p>
      ))}
    </div>
  )
}
