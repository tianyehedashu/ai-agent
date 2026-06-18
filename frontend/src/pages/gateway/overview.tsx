/**
 * AI Gateway · 概览
 *
 * 用量 KPI（与 GET /dashboard/summary 对齐；usage_aggregation=workspace|user|platform）。
 * 切片产品文案：workspace=团队（按当前选中团队），user=我（跨团队按当前账号）。
 *
 * 注：套餐毛利（margin）属于平台经营数据,**仅平台管理员**可见;
 *     已从概览页移除独立卡片;如需查看请走平台管理员专属入口
 *     （后端 API `/dashboard/margin` 仍受 platform admin 守护）。
 */

import { useMemo, useState } from 'react'
import type { ComponentType } from 'react'

import { useQuery } from '@tanstack/react-query'

import { gatewayApi, type GatewayUsageAggregation } from '@/api/gateway'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { MetricCard } from '@/components/ui/metric-card'
import { PageHeader } from '@/components/ui/page-shell'
import { GatewayQueryErrorBanner } from '@/features/gateway-shared/gateway-query-error-banner'
import { GatewayRefreshButton } from '@/features/gateway-shared/gateway-refresh-button'
import { gatewayUsageAggregationOptions } from '@/features/gateway-usage/usage-aggregation'
import { UsageAggregationToggle } from '@/features/gateway-usage/usage-aggregation-toggle'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useGatewayTeamId } from '@/hooks/use-gateway-team-id'
import { Activity, Coins, Gauge, LineChart, Timer, TrendingUp } from '@/lib/lucide-icons'

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
  const { isAdmin, isPlatformAdmin } = useGatewayPermission()
  const aggregationOptions = useMemo(
    () => gatewayUsageAggregationOptions(isPlatformAdmin),
    [isPlatformAdmin]
  )
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
    <div className="space-y-5">
      <PageHeader
        eyebrow="Gateway Console"
        title="AI Gateway 概览"
        description="从调用、成本、延迟与成功率快速判断当前模型网关的运行质量。"
        icon={LineChart}
        actions={
          <>
            <UsageAggregationToggle
              value={usageAggregation}
              onChange={setUsageAggregation}
              options={aggregationOptions}
            />
            <div className="flex items-center gap-1 rounded-lg border border-border/70 bg-card/70 p-0.5 shadow-sm">
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
          </>
        }
      />

      {isError ? (
        <GatewayQueryErrorBanner
          error={error}
          title="概览数据加载失败"
          fallback="无法加载用量概览"
        />
      ) : null}

      <div
        className={`grid grid-cols-1 gap-3 md:grid-cols-2 ${isAdmin ? 'xl:grid-cols-5' : 'xl:grid-cols-4'}`}
      >
        <Kpi
          title="请求总数"
          value={data?.total_requests ?? 0}
          loading={isLoading && !isError}
          icon={Activity}
          tone="info"
          description="所选时间窗口"
        />
        <Kpi
          title="Token 总数"
          value={totalTokens}
          loading={isLoading && !isError}
          format="kmb"
          icon={TrendingUp}
          description="输入 + 输出"
        />
        {isAdmin ? (
          <Kpi
            title="累计成本（USD）"
            value={data?.total_cost_usd}
            loading={isLoading && !isError}
            format="money"
            icon={Coins}
            tone="warning"
            description="按可见范围"
          />
        ) : null}
        <Kpi
          title="成功率"
          value={data?.success_rate ?? 0}
          loading={isLoading && !isError}
          format="percent"
          icon={Gauge}
          tone="success"
          description="请求成功占比"
        />
        <Kpi
          title="平均延迟（ms）"
          value={data?.avg_latency_ms ?? 0}
          loading={isLoading && !isError}
          format="int"
          icon={Timer}
          tone="info"
          description="端到端响应"
        />
      </div>

      <Card className="overflow-hidden">
        <CardHeader className="border-b border-border/60 bg-muted/25">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <CardTitle className="text-base">运行快照</CardTitle>
              <CardDescription>
                汇总数据来自调用日志聚合，按当前范围与身份维度计算。
              </CardDescription>
            </div>
            <div className="rounded-full border border-success/20 bg-success/10 px-3 py-1 text-xs font-medium text-success">
              {isFetching ? '同步中' : '已聚合'}
            </div>
          </div>
        </CardHeader>
        <CardContent className="grid gap-0 p-0 md:grid-cols-4">
          <SnapshotCell label="成功请求" value={data?.success_count ?? '—'} tone="success" />
          <SnapshotCell label="失败请求" value={data?.failure_count ?? '—'} tone="destructive" />
          <SnapshotCell label="输入 Token" value={data?.total_input_tokens ?? '—'} />
          <SnapshotCell label="输出 Token" value={data?.total_output_tokens ?? '—'} />
          {(data?.total_cached_tokens ?? 0) > 0 && (
            <SnapshotCell
              label="缓存读取"
              value={(data?.total_cached_tokens ?? 0).toLocaleString()}
            />
          )}
          {(data?.total_cache_creation_tokens ?? 0) > 0 && (
            <SnapshotCell
              label="缓存创建"
              value={(data?.total_cache_creation_tokens ?? 0).toLocaleString()}
            />
          )}
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
  icon,
  tone,
  description,
}: Readonly<{
  title: string
  value: number | string | null | undefined
  loading?: boolean
  format?: 'kmb' | 'money' | 'percent' | 'int'
  icon?: ComponentType<{ className?: string }>
  tone?: 'default' | 'success' | 'warning' | 'info'
  description?: string
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
    <MetricCard
      title={title}
      value={display}
      loading={loading}
      icon={icon}
      tone={tone}
      description={description}
    />
  )
}

function SnapshotCell({
  label,
  value,
  tone,
}: Readonly<{
  label: string
  value: number | string
  tone?: 'success' | 'destructive'
}>): React.JSX.Element {
  return (
    <div className="border-b border-border/60 px-5 py-4 last:border-b-0 md:border-b-0 md:border-r md:last:border-r-0">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p
        className={`mt-1 text-lg font-semibold tabular-nums ${
          tone === 'success'
            ? 'text-success'
            : tone === 'destructive'
              ? 'text-destructive'
              : 'text-foreground'
        }`}
      >
        {typeof value === 'number' ? value.toLocaleString() : value}
      </p>
    </div>
  )
}
