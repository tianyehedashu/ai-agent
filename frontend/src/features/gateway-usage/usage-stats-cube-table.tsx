import { memo } from 'react'
import type React from 'react'

import type { GatewayUsageStatsItem } from '@/api/gateway/stats'
import { GATEWAY_DISPLAY_CURRENCY } from '@/features/gateway-pricing/display-currency'
import { formatMoney } from '@/lib/money'
import { formatCompact, formatPercent } from '@/lib/number'
import { cn } from '@/lib/utils'

export interface UsageStatsCubeTableProps {
  items: readonly GatewayUsageStatsItem[]
  maxRequests: number
  showCost: boolean
}

const CubeRow = memo(function CubeRow({
  item,
  maxRequests,
  showCost,
}: Readonly<{
  item: GatewayUsageStatsItem
  maxRequests: number
  showCost: boolean
}>): React.JSX.Element {
  const width = Math.max(4, (item.requests / maxRequests) * 100)
  const parts = item.label_parts ?? item.label.split(' / ')
  const userLabel = parts[0] ?? item.label
  const modelLabel = parts[1] ?? '-'
  const credentialLabel = parts[2] ?? '-'

  return (
    <tr className="cv-auto-row border-b last:border-0 hover:bg-muted/20">
      <td className="px-4 py-3">
        <div className="truncate font-medium">{userLabel}</div>
      </td>
      <td className="px-4 py-3">
        <div className="truncate">{modelLabel}</div>
      </td>
      <td className="px-4 py-3">
        <div className="truncate">{credentialLabel}</div>
      </td>
      <td className="px-4 py-3">
        <div className="flex min-w-[180px] items-center gap-3">
          <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-primary"
              style={{ width: `${width.toString()}%` }}
            />
          </div>
          <span className="w-16 text-right tabular-nums">{item.requests.toLocaleString()}</span>
        </div>
      </td>
      <td className="px-4 py-3 text-right tabular-nums">
        <span
          className={cn(
            item.success_rate >= 0.98
              ? 'text-emerald-600'
              : item.success_rate >= 0.9
                ? 'text-amber-600'
                : 'text-destructive'
          )}
        >
          {formatPercent(item.success_rate)}
        </span>
      </td>
      <td className="px-4 py-3 text-right tabular-nums">{formatCompact(item.total_tokens)}</td>
      {showCost ? (
        <td className="px-4 py-3 text-right tabular-nums">
          {formatMoney(item.cost_usd, {
            currency: GATEWAY_DISPLAY_CURRENCY,
            precision: 4,
          })}
        </td>
      ) : null}
      <td className="px-4 py-3 text-right tabular-nums">{formatPercent(item.cache_hit_rate)}</td>
      <td className="px-4 py-3 text-right tabular-nums">
        {Math.round(item.avg_latency_ms).toLocaleString()}ms
      </td>
    </tr>
  )
})

export const UsageStatsCubeTable = memo(function UsageStatsCubeTable({
  items,
  maxRequests,
  showCost,
}: Readonly<UsageStatsCubeTableProps>): React.JSX.Element {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[1040px] text-sm">
        <thead className="border-b bg-muted/30 text-xs uppercase text-muted-foreground">
          <tr>
            <th className="w-[180px] px-4 py-2 text-left font-medium">用户</th>
            <th className="w-[160px] px-4 py-2 text-left font-medium">模型</th>
            <th className="min-w-[180px] px-4 py-2 text-left font-medium">凭据</th>
            <th className="px-4 py-2 text-left font-medium">请求</th>
            <th className="px-4 py-2 text-right font-medium">成功率</th>
            <th className="px-4 py-2 text-right font-medium">Tokens</th>
            {showCost ? <th className="px-4 py-2 text-right font-medium">成本</th> : null}
            <th className="px-4 py-2 text-right font-medium">缓存</th>
            <th className="px-4 py-2 text-right font-medium">延迟</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <CubeRow
              key={item.group_key_parts?.join('-') ?? `${item.group_key}-${item.label}`}
              item={item}
              maxRequests={maxRequests}
              showCost={showCost}
            />
          ))}
        </tbody>
      </table>
    </div>
  )
})
