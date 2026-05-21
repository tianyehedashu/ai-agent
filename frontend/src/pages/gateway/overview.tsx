/**
 * AI Gateway · 概览
 *
 * 用量 KPI（与 GET /dashboard/summary 对齐；usage_aggregation=user|workspace）。
 * 切片产品文案：workspace=团队（按当前选中团队），user=我（跨团队按当前账号）。
 */

import { useMemo, useState } from 'react'

import { useQuery } from '@tanstack/react-query'

import { gatewayApi, type GatewayUsageAggregation, type MarginSummary } from '@/api/gateway'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { marginGroupRowTitle } from '@/features/gateway-usage/credential-display'
import { UsageAggregationToggle } from '@/features/gateway-usage/usage-aggregation-toggle'
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
  const [range, setRange] = useState<'1d' | '7d' | '30d'>('7d')
  const [usageAggregation, setUsageAggregation] = useState<GatewayUsageAggregation>('user')
  const days = useMemo(() => RANGE_DAYS.find((r) => r.value === range)?.days ?? 7, [range])

  const { data, isLoading } = useQuery({
    queryKey: ['gateway', 'dashboard', teamId, usageAggregation, days],
    queryFn: () => gatewayApi.dashboard(teamId, { days, usage_aggregation: usageAggregation }),
  })
  const { data: margin, isLoading: marginLoading } = useQuery({
    queryKey: ['gateway', 'dashboard', 'margin', teamId, days, 'credential'],
    queryFn: () => gatewayApi.dashboardMargin(teamId, { days, group_by: 'credential' }),
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
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-5">
        <Kpi title="请求总数" value={data?.total_requests ?? 0} loading={isLoading} />
        <Kpi title="Token 总数" value={totalTokens} loading={isLoading} format="kmb" />
        <Kpi
          title="累计成本（USD）"
          value={data?.total_cost_usd}
          loading={isLoading}
          format="money"
        />
        <Kpi title="成功率" value={data?.success_rate ?? 0} loading={isLoading} format="percent" />
        <Kpi
          title="平均延迟（ms）"
          value={data?.avg_latency_ms ?? 0}
          loading={isLoading}
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

      <MarginSummaryCard margin={margin} loading={marginLoading} />
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

function MarginSummaryCard({
  margin,
  loading,
}: Readonly<{
  margin: MarginSummary | undefined
  loading?: boolean
}>): React.JSX.Element {
  const revenue = coalesceNumber(margin?.total_revenue_usd)
  const cost = coalesceNumber(margin?.total_cost_usd)
  const gross = coalesceNumber(margin?.total_margin_usd)
  const rate = revenue > 0 ? gross / revenue : 0
  const topItems = margin?.items.slice(0, 5) ?? []
  const groupColumnLabel = margin?.group_column_label ?? '凭据'

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">套餐毛利</CardTitle>
        <CardDescription>
          按客户套餐收入与厂商套餐成本对齐，帮助识别高成本凭据或低毛利模型。
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <MiniKpi title="收入" value={loading ? '—' : `$${revenue.toFixed(4)}`} />
          <MiniKpi title="成本" value={loading ? '—' : `$${cost.toFixed(4)}`} />
          <MiniKpi title="毛利" value={loading ? '—' : `$${gross.toFixed(4)}`} />
          <MiniKpi title="毛利率" value={loading ? '—' : `${(rate * 100).toFixed(2)}%`} />
        </div>
        {topItems.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            {loading ? '加载中…' : '暂无套餐收入/成本数据。'}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b text-xs text-muted-foreground">
                <tr>
                  <th className="py-2 text-left font-medium">{groupColumnLabel}</th>
                  <th className="py-2 text-right font-medium">收入</th>
                  <th className="py-2 text-right font-medium">成本</th>
                  <th className="py-2 text-right font-medium">毛利</th>
                </tr>
              </thead>
              <tbody>
                {topItems.map((item) => (
                  <tr key={item.group_key || '__unlinked__'} className="border-b last:border-0">
                    <td
                      className="py-2 text-sm"
                      title={marginGroupRowTitle(item.label, item.group_key)}
                    >
                      {item.label}
                    </td>
                    <td className="py-2 text-right tabular-nums">
                      ${coalesceNumber(item.revenue_usd).toFixed(4)}
                    </td>
                    <td className="py-2 text-right tabular-nums">
                      ${coalesceNumber(item.cost_usd).toFixed(4)}
                    </td>
                    <td className="py-2 text-right tabular-nums">
                      ${coalesceNumber(item.margin_usd).toFixed(4)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function MiniKpi({ title, value }: Readonly<{ title: string; value: string }>): React.JSX.Element {
  return (
    <div className="rounded-lg border p-3">
      <p className="text-xs text-muted-foreground">{title}</p>
      <p className="mt-1 text-lg font-semibold tabular-nums">{value}</p>
    </div>
  )
}
