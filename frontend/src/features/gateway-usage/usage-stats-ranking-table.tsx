import { memo, useCallback } from 'react'
import type React from 'react'

import type { QuotaRule } from '@/api/gateway/quota-rules'
import type { GatewayUsageStatsItem } from '@/api/gateway/stats'
import { Button } from '@/components/ui/button'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { GATEWAY_DISPLAY_CURRENCY } from '@/features/gateway-pricing/display-currency'
import { UsageStatsBreakdownCredentials } from '@/features/gateway-usage/usage-stats-breakdown-credentials'
import { UsageStatsBreakdownPrimary } from '@/features/gateway-usage/usage-stats-breakdown-primary'
import { UsageStatsQuotaCell } from '@/features/gateway-usage/usage-stats-quota-cell'
import type { UsageStatsRowBreakdown } from '@/features/gateway-usage/use-usage-stats-breakdown-batch'
import { BarChart3, Shield } from '@/lib/lucide-icons'
import { coalesceMoney, formatMoney } from '@/lib/money'
import { formatCompact, formatPercent } from '@/lib/number'
import { cn } from '@/lib/utils'

export interface UsageStatsRankingTableProps {
  items: readonly GatewayUsageStatsItem[]
  maxRequests: number
  showCost: boolean
  showBreakdownCols: boolean
  identityColumnHeaders: readonly [string, string, string]
  breakdownByRowKey: ReadonlyMap<string, UsageStatsRowBreakdown>
  loadingRowKeys: ReadonlySet<string>
  credentialTopN: number
  /** 行 group_key → 对应平台配额规则；提供则展示「配额」列 */
  quotaByRowKey?: ReadonlyMap<string, QuotaRule>
  onDrill: (item: GatewayUsageStatsItem) => void
  onShowDetail: (item: GatewayUsageStatsItem) => void
  onSetQuota?: (item: GatewayUsageStatsItem) => void
}

const StatsRow = memo(function StatsRow({
  item,
  maxRequests,
  showCost,
  showBreakdownCols,
  rowBreakdown,
  rowBreakdownLoading,
  credentialTopN,
  showQuota,
  quotaRule,
  onDrill,
  onShowDetail,
  onSetQuota,
}: Readonly<{
  item: GatewayUsageStatsItem
  maxRequests: number
  showCost: boolean
  showBreakdownCols: boolean
  rowBreakdown?: UsageStatsRowBreakdown
  rowBreakdownLoading: boolean
  credentialTopN: number
  showQuota: boolean
  quotaRule?: QuotaRule
  onDrill: (item: GatewayUsageStatsItem) => void
  onShowDetail: (item: GatewayUsageStatsItem) => void
  onSetQuota?: (item: GatewayUsageStatsItem) => void
}>): React.JSX.Element {
  const width = Math.max(4, (item.requests / maxRequests) * 100)
  const rowKey = item.group_key.trim()
  const canDrill = rowKey.length > 0

  const handleDrill = useCallback(() => {
    onDrill(item)
  }, [item, onDrill])

  const handleShowDetail = useCallback(() => {
    onShowDetail(item)
  }, [item, onShowDetail])

  const handleSetQuota = useCallback(() => {
    onSetQuota?.(item)
  }, [item, onSetQuota])

  return (
    <tr className="cv-auto-row border-b last:border-0 hover:bg-muted/20">
      <td className="px-4 py-3">
        <button
          type="button"
          className={cn(
            'min-w-0 text-left',
            canDrill && 'cursor-pointer rounded-sm hover:underline'
          )}
          disabled={!canDrill}
          onClick={canDrill ? handleDrill : undefined}
          title={canDrill ? '点击钻取下一维度' : undefined}
        >
          <div className="truncate font-medium">{item.label}</div>
          {item.group_key ? (
            <div className="truncate font-mono text-[10px] text-muted-foreground">
              {item.group_key}
            </div>
          ) : null}
        </button>
      </td>
      {showBreakdownCols ? (
        <>
          <td className="px-4 py-3 align-top">
            <UsageStatsBreakdownPrimary data={rowBreakdown?.model} loading={rowBreakdownLoading} />
          </td>
          <td className="px-4 py-3 align-top">
            <UsageStatsBreakdownCredentials
              data={rowBreakdown?.credential}
              loading={rowBreakdownLoading}
              requestedTopN={credentialTopN}
            />
          </td>
        </>
      ) : null}
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
          {formatMoney(coalesceMoney(item.cost_usd), {
            currency: GATEWAY_DISPLAY_CURRENCY,
            precision: 4,
          })}
        </td>
      ) : null}
      <td className="px-4 py-3 text-right tabular-nums">
        <Tooltip>
          <TooltipTrigger asChild>
            <span className="cursor-help">{formatPercent(item.cache_hit_rate)}</span>
          </TooltipTrigger>
          <TooltipContent side="top">
            <div className="space-y-0.5 text-xs">
              <div>{item.cache_hit_count.toLocaleString()} 次命中</div>
              <div>{item.cached_tokens.toLocaleString()} cached tokens (读)</div>
              {item.cache_creation_tokens > 0 && (
                <div>{item.cache_creation_tokens.toLocaleString()} cache creation (写)</div>
              )}
            </div>
          </TooltipContent>
        </Tooltip>
      </td>
      <td className="px-4 py-3 text-right tabular-nums">
        {Math.round(item.avg_latency_ms).toLocaleString()}ms
      </td>
      {showQuota ? (
        <td className="px-4 py-3">
          <UsageStatsQuotaCell rule={quotaRule} />
        </td>
      ) : null}
      <td className="px-4 py-3 text-right">
        <div className="flex items-center justify-end gap-1">
          {onSetQuota ? (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-8 gap-1 px-2 text-xs"
              onClick={handleSetQuota}
            >
              <Shield className="h-3.5 w-3.5" />
              配额
            </Button>
          ) : null}
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-8 gap-1 px-2 text-xs"
            onClick={handleShowDetail}
          >
            <BarChart3 className="h-3.5 w-3.5" />
            分布
          </Button>
        </div>
      </td>
    </tr>
  )
})

export const UsageStatsRankingTable = memo(function UsageStatsRankingTable({
  items,
  maxRequests,
  showCost,
  showBreakdownCols,
  identityColumnHeaders,
  breakdownByRowKey,
  loadingRowKeys,
  credentialTopN,
  quotaByRowKey,
  onDrill,
  onShowDetail,
  onSetQuota,
}: Readonly<UsageStatsRankingTableProps>): React.JSX.Element {
  const showQuota = quotaByRowKey !== undefined
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[1040px] text-sm">
        <thead className="border-b bg-muted/30 text-xs uppercase text-muted-foreground">
          <tr>
            {showBreakdownCols ? (
              <>
                <th className="w-[200px] px-4 py-2 text-left font-medium">
                  {identityColumnHeaders[0]}
                </th>
                <th className="w-[140px] px-4 py-2 text-left font-medium">
                  {identityColumnHeaders[1]}
                </th>
                <th className="min-w-[200px] px-4 py-2 text-left font-medium">
                  {identityColumnHeaders[2]}
                </th>
              </>
            ) : (
              <th className="w-[220px] px-4 py-2 text-left font-medium">维度</th>
            )}
            <th className="px-4 py-2 text-left font-medium">请求</th>
            <th className="px-4 py-2 text-right font-medium">成功率</th>
            <th className="px-4 py-2 text-right font-medium">Tokens</th>
            {showCost ? <th className="px-4 py-2 text-right font-medium">成本</th> : null}
            <th className="px-4 py-2 text-right font-medium">缓存</th>
            <th className="px-4 py-2 text-right font-medium">延迟</th>
            {showQuota ? (
              <th className="w-[140px] px-4 py-2 text-right font-medium">配额</th>
            ) : null}
            <th className="w-[120px] px-4 py-2 text-right font-medium">操作</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => {
            const rowKey = item.group_key.trim()
            return (
              <StatsRow
                key={`${item.group_key}-${item.label}`}
                item={item}
                maxRequests={maxRequests}
                showCost={showCost}
                showBreakdownCols={showBreakdownCols}
                rowBreakdown={breakdownByRowKey.get(rowKey)}
                rowBreakdownLoading={loadingRowKeys.has(rowKey)}
                credentialTopN={credentialTopN}
                showQuota={showQuota}
                quotaRule={quotaByRowKey?.get(item.group_key)}
                onDrill={onDrill}
                onShowDetail={onShowDetail}
                onSetQuota={onSetQuota}
              />
            )
          })}
        </tbody>
      </table>
    </div>
  )
})
