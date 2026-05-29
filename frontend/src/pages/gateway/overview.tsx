/**
 * AI Gateway · 概览
 *
 * 用量 KPI（与 GET /dashboard/summary 对齐；usage_aggregation=user|workspace）。
 * 切片产品文案：workspace=团队（按当前选中团队），user=我（跨团队按当前账号）。
 *
 * 注：套餐毛利（margin）属于平台经营数据,**仅平台管理员**可见;
 *     已从概览页移除独立卡片;如需查看请走平台管理员专属入口
 *     （后端 API `/dashboard/margin` 仍受 platform admin 守护）。
 */

import { useMemo, useState } from 'react'

import { useQuery } from '@tanstack/react-query'

import { gatewayApi, type GatewayUsageAggregation } from '@/api/gateway'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { GatewayQueryErrorBanner } from '@/features/gateway-shared/gateway-query-error-banner'
import { GatewayRefreshButton } from '@/features/gateway-shared/gateway-refresh-button'
import { UsageAggregationToggle } from '@/features/gateway-usage/usage-aggregation-toggle'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useGatewayTeamId } from '@/hooks/use-gateway-team-id'

const RANGE_DAYS: { value: '1d' | '7d' | '30d'; days: number; label: string }[] = [
  { value: '1d', days: 1, label: '24 小时' },
  { value: '7d', days: 7, label: '7 天' },
  { value: '30d', days: 30, label: '30 天' },
]

/** 与后端 Decimal / JSON 数字字符串等对齐，避免对非 number 调用 toFixed */
function coalesceNumber(value: unknown): number {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string' && value.trim() !== '') {
    const n = Number(value)
    if (Number.isFinite(n)) return n
  }
  return 0
}

export default function GatewayOverviewPage(): React.JSX.Element {
  const teamId = useGatewayTeamId()
  const { isAdmin } = useGatewayPermission()
  const [range, setRange] = useState<'1d' | '7d' | '30d'>('7d')
  const [usageAggregation, setUsageAggregation] = useState<GatewayUsageAggregation>('user')
  const days = useMemo(() => RANGE_DAYS.find((r) => r.value === range)?.days ?? 7, [range])

  const { data, isLoading, isError, error, isFetching, refetch } = useQuery({
    queryKey: ['gateway', 'dashboard', teamId, usageAggregation, days],
    queryFn: () => gatewayApi.dashboard(teamId, { days, usage_aggregation: usageAggregation }),
  })

  const totalTokens = useMemo(() => {
    if (!data) return 0
    return coalesceNumber(data.total_input_tokens) + coalesceNumber(data.total_output_tokens)
  }, [data])

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h2 className="text-2xl font-semibold tracking-tight">概览</h2>
        <div className="flex flex-wrap items-center gap-2">
          <UsageAggregationToggle value={usageAggregation} onChange={setUsageAggregation} />
          <div className="flex items-center gap-1 rounded-md border bg-background p-0.5">
            {RANGE_DAYS.map((r) => (
              <Button
                key={r.value}
                size="sm"
                variant={range === r.value ? 'default' : 'ghost'}
                className="h-7 px-3 text-xs"
                onClick={() => {
                  setRange(r.value)
                }}
              >
                {r.label}
              </Button>
            ))}
          </div>
          <GatewayRefreshButton
            isFetching={isFetching}
            ariaLabel="刷新概览"
            onRefresh={() => refetch()}
          />
        </div>
      </div>

      {isError ? (
        <GatewayQueryErrorBanner
          error={error}
          title="概览数据加载失败"
          fallback="无法加载用量概览"
        />
      ) : null}

      <div
        className={`grid grid-cols-1 gap-3 md:grid-cols-2 ${isAdmin ? 'lg:grid-cols-5' : 'lg:grid-cols-4'}`}
      >
        <Kpi title="请求总数" value={data?.total_requests ?? 0} loading={isLoading && !isError} />
        <Kpi title="Token 总数" value={totalTokens} loading={isLoading && !isError} format="kmb" />
        {isAdmin ? (
          <Kpi
            title="累计成本（USD）"
            value={data?.total_cost_usd}
            loading={isLoading && !isError}
            format="money"
          />
        ) : null}
        <Kpi
          title="成功率"
          value={data?.success_rate ?? 0}
          loading={isLoading && !isError}
          format="percent"
        />
        <Kpi
          title="平均延迟（ms）"
          value={data?.avg_latency_ms ?? 0}
          loading={isLoading && !isError}
          format="int"
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">趋势与明细</CardTitle>
          <CardDescription>
            汇总数据来自调用日志聚合。小时级时间序列可在后端扩展
            <code className="mx-1 rounded bg-muted px-1 text-xs">gateway_metrics_hourly</code>
            后在此展示图表。
          </CardDescription>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          成功 {data?.success_count ?? '—'} / 失败 {data?.failure_count ?? '—'} · 输入 Token{' '}
          {data?.total_input_tokens ?? '—'} · 输出 Token {data?.total_output_tokens ?? '—'}
        </CardContent>
      </Card>
    </div>
  )
}

function Kpi({
  title,
  value,
  loading,
  format,
}: Readonly<{
  title: string
  value: number | string | null | undefined
  loading?: boolean
  format?: 'kmb' | 'money' | 'percent' | 'int'
}>): React.JSX.Element {
  const n = coalesceNumber(value)
  let display: string = String(n)
  if (format === 'money') display = `$${n.toFixed(4)}`
  else if (format === 'percent') display = `${(n * 100).toFixed(2)}%`
  else if (format === 'int') display = String(Math.round(n))
  else if (format === 'kmb') {
    if (n >= 1_000_000) display = `${(n / 1_000_000).toFixed(2)}M`
    else if (n >= 1_000) display = `${(n / 1_000).toFixed(2)}K`
  }
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-xs font-medium text-muted-foreground">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-semibold tabular-nums">{loading ? '—' : display}</div>
      </CardContent>
    </Card>
  )
}
