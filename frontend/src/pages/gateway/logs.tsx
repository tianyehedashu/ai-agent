/**
 * AI Gateway · 调用日志
 */

import type { ReactNode } from 'react'
import { useEffect, useMemo, useRef, useState } from 'react'

import { useInfiniteQuery, useQuery } from '@tanstack/react-query'
import { useVirtualizer, type VirtualItem } from '@tanstack/react-virtual'

import {
  gatewayApi,
  type GatewayLogDetail,
  type GatewayLogItem,
  type GatewayUsageAggregation,
} from '@/api/gateway'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { GATEWAY_DISPLAY_CURRENCY } from '@/features/gateway-pricing/display-currency'
import { GatewayRefreshButton } from '@/features/gateway-shared/gateway-refresh-button'
import {
  credentialDisplayText,
  credentialDisplayTitle,
} from '@/features/gateway-usage/credential-display'
import { LogPricingBreakdown } from '@/features/gateway-usage/log-pricing-breakdown'
import { UsageAggregationToggle } from '@/features/gateway-usage/usage-aggregation-toggle'
import { useGatewayTeamId } from '@/hooks/use-gateway-team-id'
import {
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  CircleDashed,
  Clock,
  Copy,
  Database,
  Receipt,
  Route,
  Server,
  ShieldAlert,
  Users,
  X,
  XCircle,
  Zap,
} from '@/lib/lucide-icons'
import { coalesceMoney, formatMoney } from '@/lib/money'
import { cn } from '@/lib/utils'

const PAGE_SIZE = 100

const STATUS_FILTERS: readonly { value: string; label: string }[] = [
  { value: 'all', label: '全部状态' },
  { value: 'success', label: '成功' },
  { value: 'failed', label: '失败' },
  { value: 'rate_limited', label: '限流' },
  { value: 'budget_exceeded', label: '预算超限' },
  { value: 'guardrail_blocked', label: '安全拦截' },
]

const CAPABILITY_FILTERS: readonly { value: string; label: string }[] = [
  { value: 'all', label: '全部能力' },
  { value: 'chat', label: 'Chat' },
  { value: 'embedding', label: 'Embedding' },
  { value: 'image', label: 'Image' },
  { value: 'audio_transcription', label: 'Audio STT' },
  { value: 'audio_speech', label: 'Audio TTS' },
  { value: 'rerank', label: 'Rerank' },
]

/** 表头与行共用，避免列宽漂移 */
const LOG_GRID_COLS =
  'grid grid-cols-[156px_178px_142px_104px_108px_104px_92px_92px_minmax(240px,1fr)]'

export default function GatewayLogsPage(): React.JSX.Element {
  const teamId = useGatewayTeamId()
  const parentRef = useRef<HTMLDivElement>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState('all')
  const [capabilityFilter, setCapabilityFilter] = useState('all')
  const [usageAggregation, setUsageAggregation] = useState<GatewayUsageAggregation>('user')
  const [copiedRequestId, setCopiedRequestId] = useState(false)

  const resetListPosition = (): void => {
    setSelectedId(null)
    parentRef.current?.scrollTo({ top: 0 })
  }

  const { data, fetchNextPage, hasNextPage, isFetching, isLoading, refetch } = useInfiniteQuery({
    queryKey: ['gateway', 'logs', teamId, usageAggregation, statusFilter, capabilityFilter],
    initialPageParam: 1,
    queryFn: ({ pageParam }: { pageParam: number }) =>
      gatewayApi.listLogs(teamId, {
        usage_aggregation: usageAggregation,
        page: pageParam,
        page_size: PAGE_SIZE,
        status: statusFilter === 'all' ? undefined : statusFilter,
        capability: capabilityFilter === 'all' ? undefined : capabilityFilter,
      }),
    getNextPageParam: (lastPage, all) => {
      const fetched = all.reduce((sum, p) => sum + p.items.length, 0)
      return fetched < lastPage.total ? all.length + 1 : undefined
    },
  })

  const items = useMemo<GatewayLogItem[]>(() => data?.pages.flatMap((p) => p.items) ?? [], [data])
  const totalCount = data?.pages[0]?.total ?? 0
  const hasFilters = statusFilter !== 'all' || capabilityFilter !== 'all'

  const virtualizer = useVirtualizer({
    count: items.length + (hasNextPage ? 1 : 0),
    getScrollElement: () => parentRef.current,
    estimateSize: () => 48,
    overscan: 8,
  })

  const virtualItems = virtualizer.getVirtualItems()
  const lastVisibleIndex =
    virtualItems.length > 0 ? (virtualItems[virtualItems.length - 1]?.index ?? -1) : -1

  useEffect(() => {
    if (items.length === 0 || !hasNextPage || isFetching) return
    if (lastVisibleIndex >= items.length - 1) {
      void fetchNextPage()
    }
  }, [lastVisibleIndex, items.length, hasNextPage, isFetching, fetchNextPage])

  const selectedItem = useMemo(
    () => items.find((item) => item.id === selectedId),
    [items, selectedId]
  )

  const { data: detail } = useQuery({
    queryKey: ['gateway', 'log', teamId, selectedId, usageAggregation],
    queryFn: () => {
      if (typeof selectedId !== 'string' || selectedId.length === 0) {
        return Promise.reject(new Error('selectedId is required when query runs'))
      }
      return gatewayApi.getLog(teamId, selectedId, { usage_aggregation: usageAggregation })
    },
    enabled: !!selectedId,
  })

  const activeLog = detail ?? selectedItem

  const clearFilters = (): void => {
    setStatusFilter('all')
    setCapabilityFilter('all')
    resetListPosition()
  }

  const copyRequestId = (value: string): void => {
    void navigator.clipboard
      .writeText(value)
      .then(() => {
        setCopiedRequestId(true)
        window.setTimeout(() => {
          setCopiedRequestId(false)
        }, 1200)
      })
      .catch(() => {
        setCopiedRequestId(false)
      })
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="min-w-0">
          <h2 className="text-2xl font-semibold tracking-tight">调用日志</h2>
          <p className="text-sm text-muted-foreground">
            {usageAggregation === 'user' ? '我的跨团队调用' : '当前团队调用'} · 已载入{' '}
            {items.length.toLocaleString()} / {totalCount.toLocaleString()} 条
          </p>
        </div>
        <UsageAggregationToggle
          value={usageAggregation}
          onChange={(next) => {
            setUsageAggregation(next)
            resetListPosition()
          }}
        />
      </div>

      <div className="flex flex-col gap-2 rounded-lg border bg-background p-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-wrap items-center gap-2">
          <Select
            value={statusFilter}
            onValueChange={(next) => {
              setStatusFilter(next)
              resetListPosition()
            }}
          >
            <SelectTrigger className="h-9 w-[136px]" aria-label="按状态筛选">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {STATUS_FILTERS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select
            value={capabilityFilter}
            onValueChange={(next) => {
              setCapabilityFilter(next)
              resetListPosition()
            }}
          >
            <SelectTrigger className="h-9 w-[152px]" aria-label="按能力筛选">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {CAPABILITY_FILTERS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {hasFilters ? (
            <Button size="sm" variant="ghost" className="h-9 gap-1.5" onClick={clearFilters}>
              <X className="h-4 w-4" />
              清空筛选
            </Button>
          ) : null}
          <GatewayRefreshButton
            isFetching={isFetching}
            ariaLabel="刷新日志"
            onRefresh={() => refetch()}
          />
        </div>
      </div>

      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <div className="min-w-[1220px]">
            <div
              className={`${LOG_GRID_COLS} border-b bg-muted/30 px-3 py-2 text-xs font-medium text-muted-foreground`}
            >
              <div>时间</div>
              <div>模型</div>
              <div>凭据</div>
              <div>能力</div>
              <div>状态</div>
              <div className="text-right">Tokens</div>
              <div className="text-right">成本</div>
              <div className="text-right">延迟</div>
              <div>请求 ID</div>
            </div>
            <div ref={parentRef} className="h-[560px] overflow-auto">
              {isLoading ? (
                <ListState
                  icon={<CircleDashed className="h-5 w-5 animate-spin" />}
                  title="加载中"
                />
              ) : items.length === 0 ? (
                <ListState
                  icon={<Database className="h-5 w-5" />}
                  title={hasFilters ? '没有匹配日志' : '暂无调用日志'}
                  action={
                    hasFilters ? (
                      <Button size="sm" variant="outline" onClick={clearFilters}>
                        清空筛选
                      </Button>
                    ) : undefined
                  }
                />
              ) : (
                <div
                  style={{
                    height: `${virtualizer.getTotalSize().toString()}px`,
                    width: '100%',
                    position: 'relative',
                  }}
                >
                  {virtualItems.map((row: VirtualItem) => {
                    if (row.index >= items.length) {
                      return (
                        <div
                          key={row.key}
                          style={{
                            position: 'absolute',
                            top: 0,
                            left: 0,
                            width: '100%',
                            height: `${row.size.toString()}px`,
                            transform: `translateY(${row.start.toString()}px)`,
                          }}
                          className="flex items-center justify-center px-3 text-xs text-muted-foreground"
                        >
                          加载更多...
                        </div>
                      )
                    }
                    const item = row.index < items.length ? items[row.index] : undefined
                    if (item === undefined) return null
                    return (
                      <LogRow
                        key={row.key}
                        row={row}
                        item={item}
                        selected={item.id === selectedId}
                        onSelect={() => {
                          setSelectedId(item.id)
                        }}
                      />
                    )
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
        <div className="flex items-center justify-between gap-2 border-t px-3 py-2 text-xs text-muted-foreground">
          <span>{isFetching && !isLoading ? '正在同步...' : ' '}</span>
          {hasNextPage ? (
            <Button
              size="sm"
              variant="outline"
              onClick={() => void fetchNextPage()}
              disabled={isFetching}
            >
              {isFetching ? '加载中...' : '加载更多'}
            </Button>
          ) : null}
        </div>
      </Card>

      <Sheet
        open={!!selectedId}
        onOpenChange={(v) => {
          if (!v) {
            setSelectedId(null)
            setCopiedRequestId(false)
          }
        }}
      >
        <SheetContent className="flex max-h-[100vh] w-full flex-col p-0 sm:max-w-2xl">
          <SheetHeader className="shrink-0 border-b px-5 pb-4 pt-5 text-left">
            <div className="flex min-w-0 flex-wrap items-center gap-2 pr-8">
              {activeLog ? <StatusBadge status={activeLog.status} /> : null}
              <SheetTitle className="min-w-0 truncate text-base">
                {activeLog?.real_model ?? activeLog?.route_name ?? '请求详情'}
              </SheetTitle>
            </div>
            <SheetDescription className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1 font-mono text-xs">
              <span>{activeLog ? formatDateTime(activeLog.created_at) : '加载中...'}</span>
              {activeLog?.request_id ? (
                <button
                  type="button"
                  className="inline-flex min-w-0 items-center gap-1 rounded px-1 py-0.5 text-left hover:bg-muted"
                  title="复制请求 ID"
                  onClick={() => {
                    copyRequestId(activeLog.request_id ?? '')
                  }}
                >
                  <Copy className="h-3.5 w-3.5 shrink-0" />
                  <span className="truncate">{activeLog.request_id}</span>
                  {copiedRequestId ? <span className="text-emerald-600">已复制</span> : null}
                </button>
              ) : null}
            </SheetDescription>
          </SheetHeader>

          {selectedId !== null && activeLog === undefined ? (
            <div className="p-5 text-sm text-muted-foreground">加载中...</div>
          ) : null}

          {activeLog !== undefined ? (
            <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
              <LogMetricGrid log={activeLog} />

              <div className="mt-4 space-y-3">
                {activeLog.status !== 'success' ||
                activeLog.error_code ||
                activeLog.error_message ? (
                  <DetailSection
                    title="异常"
                    icon={<ShieldAlert className="h-4 w-4 text-destructive" />}
                  >
                    <dl className="grid grid-cols-[92px_1fr] gap-x-3 gap-y-2 text-xs">
                      <DetailField label="错误码" mono>
                        {activeLog.error_code ?? '—'}
                      </DetailField>
                      <DetailField label="错误信息">{activeLog.error_message ?? '—'}</DetailField>
                    </dl>
                  </DetailSection>
                ) : null}

                <DetailSection title="调用路径" icon={<Route className="h-4 w-4" />}>
                  <dl className="grid grid-cols-[92px_1fr] gap-x-3 gap-y-2 text-xs">
                    <DetailField label="客户端模型" mono>
                      {activeLog.route_name ?? '—'}
                    </DetailField>
                    <DetailField label="部署模型" mono>
                      <span>{activeLog.deployment_model_name ?? activeLog.real_model ?? '—'}</span>
                      {activeLog.deployment_gateway_model_id ? (
                        <span className="mt-0.5 block text-muted-foreground">
                          {activeLog.deployment_gateway_model_id}
                        </span>
                      ) : null}
                    </DetailField>
                    <DetailField label="提供商">{activeLog.provider ?? '—'}</DetailField>
                    <DetailField label="能力">{capabilityLabel(activeLog.capability)}</DetailField>
                    <DetailField label="回退链" mono>
                      {activeLog.fallback_chain.length > 0
                        ? activeLog.fallback_chain.join(' → ')
                        : '—'}
                    </DetailField>
                  </dl>
                </DetailSection>

                <DetailSection title="身份与凭据" icon={<Users className="h-4 w-4" />}>
                  <dl className="grid grid-cols-[92px_1fr] gap-x-3 gap-y-2 text-xs">
                    <DetailField label="统计口径">
                      {usageAggregation === 'user' ? '我（跨团队）' : '团队'}
                    </DetailField>
                    <DetailField label="用户">
                      {activeLog.user_email_snapshot ?? activeLog.user_id ?? '—'}
                    </DetailField>
                    <DetailField label="团队" mono>
                      {activeLog.team_id ?? '—'}
                    </DetailField>
                    <DetailField label="凭据">
                      <span>{activeLog.credential_name_snapshot ?? '—'}</span>
                      {activeLog.credential_id ? (
                        <span className="mt-0.5 block font-mono text-muted-foreground">
                          {activeLog.credential_id}
                        </span>
                      ) : null}
                    </DetailField>
                    <DetailField label="虚拟 Key">
                      <span>{activeLog.vkey_name_snapshot ?? '—'}</span>
                      {activeLog.vkey_id ? (
                        <span className="mt-0.5 block font-mono text-muted-foreground">
                          {activeLog.vkey_id}
                        </span>
                      ) : null}
                    </DetailField>
                  </dl>
                </DetailSection>

                {detail !== undefined ? <LogPricingBreakdown detail={detail} /> : null}

                {detail !== undefined ? <LogPayloadPanels detail={detail} /> : null}
              </div>
            </div>
          ) : null}
        </SheetContent>
      </Sheet>
    </div>
  )
}

function LogRow({
  row,
  item,
  selected,
  onSelect,
}: Readonly<{
  row: VirtualItem
  item: GatewayLogItem
  selected: boolean
  onSelect: () => void
}>): React.JSX.Element {
  return (
    <button
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: '100%',
        height: `${row.size.toString()}px`,
        transform: `translateY(${row.start.toString()}px)`,
      }}
      className={cn(
        LOG_GRID_COLS,
        'cv-auto-row items-center border-b px-3 text-left text-xs transition-colors hover:bg-muted/40',
        selected ? 'bg-primary/5 ring-1 ring-inset ring-primary/20' : ''
      )}
      type="button"
      onClick={onSelect}
    >
      <div className="truncate text-muted-foreground">{formatDateTime(item.created_at)}</div>
      <div className="truncate font-mono" title={item.real_model ?? item.route_name ?? undefined}>
        {item.real_model ?? item.route_name ?? '—'}
      </div>
      <div className="truncate" title={credentialDisplayTitle(item)}>
        {credentialDisplayText(item)}
      </div>
      <div>
        <CapabilityBadge capability={item.capability} />
      </div>
      <div>
        <StatusBadge status={item.status} />
      </div>
      <div className="text-right tabular-nums">
        {(item.input_tokens + item.output_tokens).toLocaleString()}
      </div>
      <div className="text-right tabular-nums">{formatLogMoney(item)}</div>
      <div className="text-right tabular-nums">{formatMs(item.latency_ms)}</div>
      <div className="truncate font-mono text-muted-foreground">{item.request_id ?? item.id}</div>
    </button>
  )
}

function ListState({
  icon,
  title,
  action,
}: Readonly<{
  icon: ReactNode
  title: string
  action?: ReactNode
}>): React.JSX.Element {
  return (
    <div className="flex h-full min-h-[240px] flex-col items-center justify-center gap-3 px-4 py-8 text-sm text-muted-foreground">
      <div className="flex h-9 w-9 items-center justify-center rounded-full border bg-muted/30">
        {icon}
      </div>
      <div className="font-medium text-foreground">{title}</div>
      {action}
    </div>
  )
}

function LogMetricGrid({ log }: Readonly<{ log: GatewayLogItem }>): React.JSX.Element {
  return (
    <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
      <MetricTile icon={<Receipt className="h-4 w-4" />} label="计费" value={formatLogMoney(log)} />
      <MetricTile
        icon={<Zap className="h-4 w-4" />}
        label="Tokens"
        value={(log.input_tokens + log.output_tokens).toLocaleString()}
        caption={`${log.input_tokens.toLocaleString()} in / ${log.output_tokens.toLocaleString()} out`}
      />
      <MetricTile
        icon={<Clock className="h-4 w-4" />}
        label="延迟"
        value={formatMs(log.latency_ms)}
      />
      <MetricTile
        icon={<Server className="h-4 w-4" />}
        label="缓存"
        value={log.cache_hit ? '命中' : '未命中'}
        caption={log.cached_tokens > 0 ? `${log.cached_tokens.toLocaleString()} cached` : undefined}
      />
    </div>
  )
}

function MetricTile({
  icon,
  label,
  value,
  caption,
}: Readonly<{
  icon: ReactNode
  label: string
  value: string
  caption?: string
}>): React.JSX.Element {
  return (
    <div className="min-w-0 rounded-md border bg-muted/20 p-3">
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
        {icon}
        <span>{label}</span>
      </div>
      <div className="mt-1 truncate text-base font-semibold tabular-nums">{value}</div>
      {caption ? (
        <div className="mt-0.5 truncate text-[11px] text-muted-foreground">{caption}</div>
      ) : null}
    </div>
  )
}

function DetailSection({
  title,
  icon,
  children,
}: Readonly<{
  title: string
  icon: ReactNode
  children: ReactNode
}>): React.JSX.Element {
  return (
    <section className="rounded-md border bg-muted/10 p-3">
      <h3 className="mb-3 flex items-center gap-2 text-xs font-semibold text-muted-foreground">
        {icon}
        {title}
      </h3>
      {children}
    </section>
  )
}

function DetailField({
  label,
  mono,
  children,
}: Readonly<{
  label: string
  mono?: boolean
  children: ReactNode
}>): React.JSX.Element {
  return (
    <>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className={cn('min-w-0 break-words', mono ? 'font-mono text-[11px]' : '')}>{children}</dd>
    </>
  )
}

function LogPayloadPanels({ detail }: Readonly<{ detail: GatewayLogDetail }>): React.JSX.Element {
  return (
    <div className="space-y-2">
      <PayloadPanel title="Prompt（脱敏）" value={detail.prompt_redacted} />
      <PayloadPanel title="响应摘要" value={detail.response_summary} />
      <PayloadPanel
        title="快照与元数据"
        value={{
          team_snapshot: detail.team_snapshot,
          route_snapshot: detail.route_snapshot,
          metadata_extra: detail.metadata_extra,
        }}
      />
      <PayloadPanel title="完整 JSON" value={detail} />
    </div>
  )
}

function PayloadPanel({
  title,
  value,
}: Readonly<{
  title: string
  value: unknown
}>): React.JSX.Element {
  return (
    <Collapsible className="group rounded-md border">
      <CollapsibleTrigger className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs font-medium hover:bg-muted/40">
        <ChevronDown className="h-4 w-4 shrink-0 transition-transform group-data-[state=closed]:-rotate-90" />
        <span>{title}</span>
      </CollapsibleTrigger>
      <CollapsibleContent>
        <pre className="max-h-64 overflow-auto border-t bg-muted/30 p-3 font-mono text-[11px] leading-relaxed">
          {formatJson(value)}
        </pre>
      </CollapsibleContent>
    </Collapsible>
  )
}

function StatusBadge({ status }: Readonly<{ status: string }>): React.JSX.Element {
  const normalized = status.toLowerCase()
  const isSuccess = normalized === 'success'
  const isFailure = normalized === 'failed' || normalized === 'error'
  const Icon = isSuccess ? CheckCircle2 : isFailure ? XCircle : AlertCircle
  const label = statusLabel(normalized)

  return (
    <Badge
      variant="outline"
      className={cn(
        'inline-flex min-w-[76px] justify-center gap-1 border px-2 py-0.5 font-medium',
        isSuccess
          ? 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-300'
          : isFailure
            ? 'border-red-200 bg-red-50 text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300'
            : 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-300'
      )}
    >
      <Icon className="h-3 w-3" />
      {label}
    </Badge>
  )
}

function CapabilityBadge({ capability }: Readonly<{ capability: string }>): React.JSX.Element {
  return (
    <Badge variant="outline" className="max-w-[92px] justify-center truncate font-medium">
      {capabilityLabel(capability)}
    </Badge>
  )
}

function statusLabel(status: string): string {
  if (status === 'success') return '成功'
  if (status === 'failed' || status === 'error') return '失败'
  if (status === 'rate_limited') return '限流'
  if (status === 'budget_exceeded') return '预算'
  if (status === 'guardrail_blocked') return '拦截'
  return status
}

function capabilityLabel(capability: string): string {
  const found = CAPABILITY_FILTERS.find((option) => option.value === capability)
  return found?.label ?? capability
}

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(new Date(value))
}

function formatMs(value: number | null | undefined): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '—'
  return `${Math.round(value).toLocaleString()}ms`
}

function formatLogMoney(item: GatewayLogItem): string {
  return formatMoney(coalesceMoney(item.revenue_usd ?? item.cost_usd), {
    currency: GATEWAY_DISPLAY_CURRENCY,
    precision: 4,
  })
}

function formatJson(value: unknown): string {
  if (value === null || value === undefined) return '（无）'
  const json = JSON.stringify(value, null, 2)
  return json
}
