/**
 * AI Gateway · 调用统计
 */

import { memo, useCallback, useMemo, useState } from 'react'
import type React from 'react'

import { useQuery } from '@tanstack/react-query'

import { credentialsApi } from '@/api/gateway/credentials'
import { keysApi } from '@/api/gateway/keys'
import type { GatewayUsageAggregation } from '@/api/gateway/logs'
import { type GatewayModel, modelsApi } from '@/api/gateway/models'
import {
  statsApi,
  type GatewayUsageStatsGroupBy,
  type GatewayUsageStatsItem,
  type GatewayUsageStatsQuery,
} from '@/api/gateway/stats'
import { teamsApi } from '@/api/gateway/teams'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
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
import { UsageAggregationToggle } from '@/features/gateway-usage/usage-aggregation-toggle'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useGatewayTeamId } from '@/hooks/use-gateway-team-id'
import { LineChart, RefreshCw, Settings2, X } from '@/lib/lucide-icons'
import { coalesceMoney, formatMoney } from '@/lib/money'
import { cn } from '@/lib/utils'

const ALL_VALUE = '__all__'
const LIMIT = 40

const RANGE_DAYS: { value: 1 | 7 | 30 | 90; label: string }[] = [
  { value: 1, label: '24 小时' },
  { value: 7, label: '7 天' },
  { value: 30, label: '30 天' },
  { value: 90, label: '90 天' },
]

const GROUP_OPTIONS: { value: GatewayUsageStatsGroupBy; label: string }[] = [
  { value: 'credential', label: '凭据' },
  { value: 'user', label: '人员' },
  { value: 'team', label: '团队' },
  { value: 'model', label: '模型' },
  { value: 'vkey', label: '虚拟 Key' },
  { value: 'provider', label: '提供商' },
  { value: 'capability', label: '能力' },
  { value: 'status', label: '状态' },
]

const STATUS_OPTIONS = [
  { value: 'success', label: '成功' },
  { value: 'failed', label: '失败' },
  { value: 'rate_limited', label: '限流' },
  { value: 'budget_exceeded', label: '预算超限' },
  { value: 'guardrail_blocked', label: '安全拦截' },
]

const CAPABILITY_OPTIONS = [
  { value: 'chat', label: 'Chat' },
  { value: 'embedding', label: 'Embedding' },
  { value: 'image', label: 'Image' },
  { value: 'audio_transcription', label: 'Audio STT' },
  { value: 'audio_speech', label: 'Audio TTS' },
  { value: 'rerank', label: 'Rerank' },
]

type StatsFilterSource = 'credential' | 'user' | 'team' | 'model' | 'vkey' | 'provider'

interface SelectOption {
  value: string
  label: string
  meta?: string
}

function asNumber(value: unknown): number {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string' && value.trim() !== '') {
    const parsed = Number(value)
    if (Number.isFinite(parsed)) return parsed
  }
  return 0
}

function formatCompact(value: unknown): string {
  const n = asNumber(value)
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(2)}K`
  return Math.round(n).toLocaleString()
}

function formatPercent(value: unknown): string {
  return `${(asNumber(value) * 100).toFixed(1)}%`
}

function errorMessage(error: unknown): string {
  if (error instanceof Error) return error.message
  return '加载失败'
}

function resettable(value: string): string | undefined {
  return value === ALL_VALUE ? undefined : value
}

function uniqueSorted(values: string[]): SelectOption[] {
  return Array.from(new Set(values.filter((v) => v.trim().length > 0)))
    .sort((a, b) => a.localeCompare(b))
    .map((value) => ({ value, label: value }))
}

function selectedOptionLabel(options: SelectOption[], value: string): string {
  if (value === ALL_VALUE) return ''
  return options.find((option) => option.value === value)?.label ?? value
}

function modelOptionValues(models: GatewayModel[]): string[] {
  const values: string[] = []
  for (const model of models) {
    values.push(model.name)
    values.push(model.real_model)
  }
  return values
}

export default function GatewayStatsPage(): React.JSX.Element {
  const teamId = useGatewayTeamId()
  const { isAdmin } = useGatewayPermission()
  const [days, setDays] = useState<1 | 7 | 30 | 90>(7)
  const [usageAggregation, setUsageAggregation] = useState<GatewayUsageAggregation>('workspace')
  const [groupBy, setGroupBy] = useState<GatewayUsageStatsGroupBy>('credential')
  const [credentialId, setCredentialId] = useState(ALL_VALUE)
  const [userId, setUserId] = useState(ALL_VALUE)
  const [teamFilterId, setTeamFilterId] = useState(ALL_VALUE)
  const [model, setModel] = useState(ALL_VALUE)
  const [provider, setProvider] = useState(ALL_VALUE)
  const [capability, setCapability] = useState(ALL_VALUE)
  const [status, setStatus] = useState(ALL_VALUE)
  const [vkeyId, setVkeyId] = useState(ALL_VALUE)
  const [filtersOpen, setFiltersOpen] = useState(false)
  const [loadedFilters, setLoadedFilters] = useState<ReadonlySet<StatsFilterSource>>(
    () => new Set()
  )

  const requestFilter = useCallback((source: StatsFilterSource): void => {
    setLoadedFilters((prev) => {
      if (prev.has(source)) return prev
      const next = new Set(prev)
      next.add(source)
      return next
    })
  }, [])

  const requestProviderFilters = useCallback((): void => {
    setLoadedFilters((prev) => {
      const next = new Set(prev)
      next.add('credential')
      next.add('model')
      next.add('provider')
      if (next.size === prev.size) return prev
      return next
    })
  }, [])

  const needsCredentialOptions =
    loadedFilters.has('credential') ||
    loadedFilters.has('provider') ||
    credentialId !== ALL_VALUE ||
    provider !== ALL_VALUE

  const credentialsQuery = useQuery({
    queryKey: ['gateway', 'credential-summaries', teamId],
    queryFn: () => credentialsApi.listCredentialSummaries(teamId),
    enabled: needsCredentialOptions,
  })
  const membersQuery = useQuery({
    queryKey: ['gateway', 'members', teamId],
    queryFn: () => teamsApi.listMembers(teamId),
    enabled: loadedFilters.has('user') || userId !== ALL_VALUE,
  })
  const teamsQuery = useQuery({
    queryKey: ['gateway', 'teams'],
    queryFn: () => teamsApi.listTeams(),
    enabled: loadedFilters.has('team') || teamFilterId !== ALL_VALUE,
  })
  const keysQuery = useQuery({
    queryKey: ['gateway', 'keys', teamId],
    queryFn: () => keysApi.listKeys(teamId),
    enabled: loadedFilters.has('vkey') || vkeyId !== ALL_VALUE,
  })
  const modelsQuery = useQuery({
    queryKey: ['gateway', 'models', teamId, 'callable'],
    queryFn: () => modelsApi.listModels(teamId, { registry_scope: 'callable' }),
    enabled:
      loadedFilters.has('model') ||
      loadedFilters.has('provider') ||
      model !== ALL_VALUE ||
      provider !== ALL_VALUE,
  })

  const credentialOptions = useMemo<SelectOption[]>(
    () =>
      (credentialsQuery.data ?? []).map((credential) => ({
        value: credential.id,
        label: credential.name,
        meta: credential.provider,
      })),
    [credentialsQuery.data]
  )
  const memberOptions = useMemo<SelectOption[]>(
    () =>
      (membersQuery.data ?? []).map((member) => ({
        value: member.user_id,
        label: member.user_name ?? member.user_email ?? member.user_id,
        meta: member.role,
      })),
    [membersQuery.data]
  )
  const teamOptions = useMemo<SelectOption[]>(
    () =>
      (teamsQuery.data ?? []).map((team) => ({
        value: team.id,
        label: team.name,
        meta: team.kind,
      })),
    [teamsQuery.data]
  )
  const keyOptions = useMemo<SelectOption[]>(
    () =>
      (keysQuery.data ?? []).map((key) => ({
        value: key.id,
        label: key.name,
        meta: key.masked_key,
      })),
    [keysQuery.data]
  )
  const modelOptions = useMemo(
    () => uniqueSorted(modelOptionValues(modelsQuery.data ?? [])),
    [modelsQuery.data]
  )
  const providerOptions = useMemo(() => {
    const values = [
      ...(credentialsQuery.data ?? []).map((credential) => credential.provider),
      ...(modelsQuery.data ?? []).map((gatewayModel) => gatewayModel.provider),
    ]
    return uniqueSorted(values)
  }, [credentialsQuery.data, modelsQuery.data])

  const queryParams = useMemo((): GatewayUsageStatsQuery => {
    return {
      days,
      usage_aggregation: usageAggregation,
      group_by: groupBy,
      credential_id: resettable(credentialId),
      user_id: resettable(userId),
      team_id: resettable(teamFilterId),
      model: resettable(model),
      provider: resettable(provider),
      capability: resettable(capability),
      status: resettable(status),
      vkey_id: resettable(vkeyId),
      limit: LIMIT,
    }
  }, [
    days,
    usageAggregation,
    groupBy,
    credentialId,
    userId,
    teamFilterId,
    model,
    provider,
    capability,
    status,
    vkeyId,
  ])

  const statsQuery = useQuery({
    queryKey: ['gateway', 'usage-stats', teamId, queryParams],
    queryFn: () => statsApi.usageStats(teamId, queryParams),
  })

  const items = statsQuery.data?.items ?? []
  const maxRequests = Math.max(...items.map((item) => item.requests), 1)
  const totals = statsQuery.data?.totals
  const activeFilters = [
    {
      key: 'credential',
      label: '凭据',
      value: selectedOptionLabel(credentialOptions, credentialId),
    },
    { key: 'user', label: '人员', value: selectedOptionLabel(memberOptions, userId) },
    { key: 'team', label: '团队', value: selectedOptionLabel(teamOptions, teamFilterId) },
    { key: 'model', label: '模型', value: selectedOptionLabel(modelOptions, model) },
    { key: 'vkey', label: '虚拟 Key', value: selectedOptionLabel(keyOptions, vkeyId) },
    { key: 'provider', label: '提供商', value: selectedOptionLabel(providerOptions, provider) },
    {
      key: 'capability',
      label: '能力',
      value: selectedOptionLabel(CAPABILITY_OPTIONS, capability),
    },
    { key: 'status', label: '状态', value: selectedOptionLabel(STATUS_OPTIONS, status) },
  ].filter((filter) => filter.value.length > 0)
  const activeFilterCount = activeFilters.length

  function clearFilters(): void {
    setCredentialId(ALL_VALUE)
    setUserId(ALL_VALUE)
    setTeamFilterId(ALL_VALUE)
    setModel(ALL_VALUE)
    setProvider(ALL_VALUE)
    setCapability(ALL_VALUE)
    setStatus(ALL_VALUE)
    setVkeyId(ALL_VALUE)
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
        <div>
          <h2 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
            <LineChart className="h-6 w-6 text-primary" />
            调用统计
          </h2>
          <p className="text-sm text-muted-foreground">
            {statsQuery.data
              ? `${new Date(statsQuery.data.start).toLocaleDateString()} - ${new Date(statsQuery.data.end).toLocaleDateString()}`
              : '按当前时间窗口聚合调用日志'}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <UsageAggregationToggle value={usageAggregation} onChange={setUsageAggregation} />
          <div className="flex flex-wrap gap-1 rounded-md border bg-background p-0.5">
            {RANGE_DAYS.map((range) => (
              <Button
                key={range.value}
                size="sm"
                variant={days === range.value ? 'default' : 'ghost'}
                className="h-7 px-3 text-xs"
                type="button"
                onClick={() => {
                  setDays(range.value)
                }}
              >
                {range.label}
              </Button>
            ))}
          </div>
          <Button
            type="button"
            size="sm"
            variant={activeFilterCount > 0 ? 'default' : 'outline'}
            className="h-9 gap-2"
            onClick={() => {
              setFiltersOpen(true)
            }}
          >
            <Settings2 className="h-4 w-4" />
            筛选
            {activeFilterCount > 0 ? (
              <Badge variant="secondary" className="ml-0.5 px-1.5">
                {activeFilterCount}
              </Badge>
            ) : null}
          </Button>
          <Button
            type="button"
            size="icon"
            variant="outline"
            className="h-9 w-9"
            title="刷新"
            aria-label="刷新统计"
            disabled={statsQuery.isFetching}
            onClick={() => {
              void statsQuery.refetch()
            }}
          >
            <RefreshCw className={cn('h-4 w-4', statsQuery.isFetching ? 'animate-spin' : '')} />
          </Button>
        </div>
      </div>

      <div className="space-y-3 rounded-lg border bg-background p-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="text-xs font-medium text-muted-foreground">分析维度</div>
          {activeFilterCount > 0 ? (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-7 gap-1.5 px-2 text-xs"
              onClick={clearFilters}
            >
              <X className="h-3.5 w-3.5" />
              清空筛选
            </Button>
          ) : null}
        </div>
        <div className="flex flex-wrap gap-1">
          {GROUP_OPTIONS.map((option) => (
            <Button
              key={option.value}
              type="button"
              size="sm"
              variant={groupBy === option.value ? 'default' : 'outline'}
              className="h-8 px-3 text-xs"
              onClick={() => {
                setGroupBy(option.value)
              }}
            >
              {option.label}
            </Button>
          ))}
        </div>
        {activeFilterCount > 0 ? (
          <div className="flex flex-wrap gap-1.5">
            {activeFilters.map((filter) => (
              <Badge
                key={filter.key}
                variant="outline"
                className="max-w-[240px] gap-1 truncate font-normal"
                title={`${filter.label}: ${filter.value}`}
              >
                <span className="text-muted-foreground">{filter.label}</span>
                <span className="truncate">{filter.value}</span>
              </Badge>
            ))}
          </div>
        ) : null}
      </div>

      <Sheet open={filtersOpen} onOpenChange={setFiltersOpen}>
        <SheetContent className="flex max-h-[100vh] w-full flex-col p-0 sm:max-w-xl">
          <SheetHeader className="shrink-0 border-b px-5 pb-4 pt-5 text-left">
            <SheetTitle className="flex items-center gap-2 pr-8 text-base">
              <Settings2 className="h-4 w-4" />
              筛选调用统计
            </SheetTitle>
            <SheetDescription>
              {usageAggregation === 'user' ? '我的跨团队调用' : '当前团队调用'} ·{' '}
              {RANGE_DAYS.find((range) => range.value === days)?.label}
            </SheetDescription>
          </SheetHeader>
          <div className="min-h-0 flex-1 space-y-5 overflow-y-auto px-5 py-4">
            <section className="space-y-3">
              <h3 className="text-xs font-semibold text-muted-foreground">对象</h3>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <FilterSelect
                  label="凭据"
                  value={credentialId}
                  onValueChange={setCredentialId}
                  onRequestOptions={() => {
                    requestFilter('credential')
                  }}
                  options={credentialOptions}
                />
                <FilterSelect
                  label="人员"
                  value={userId}
                  onValueChange={setUserId}
                  onRequestOptions={() => {
                    requestFilter('user')
                  }}
                  options={memberOptions}
                />
                <FilterSelect
                  label="团队"
                  value={teamFilterId}
                  onValueChange={setTeamFilterId}
                  onRequestOptions={() => {
                    requestFilter('team')
                  }}
                  options={teamOptions}
                />
                <FilterSelect
                  label="虚拟 Key"
                  value={vkeyId}
                  onValueChange={setVkeyId}
                  onRequestOptions={() => {
                    requestFilter('vkey')
                  }}
                  options={keyOptions}
                />
              </div>
            </section>

            <section className="space-y-3">
              <h3 className="text-xs font-semibold text-muted-foreground">模型</h3>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <FilterSelect
                  label="模型"
                  value={model}
                  onValueChange={setModel}
                  onRequestOptions={() => {
                    requestFilter('model')
                  }}
                  options={modelOptions}
                />
                <FilterSelect
                  label="提供商"
                  value={provider}
                  onValueChange={setProvider}
                  onRequestOptions={requestProviderFilters}
                  options={providerOptions}
                />
              </div>
            </section>

            <section className="space-y-3">
              <h3 className="text-xs font-semibold text-muted-foreground">调用</h3>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <FilterSelect
                  label="能力"
                  value={capability}
                  onValueChange={setCapability}
                  options={CAPABILITY_OPTIONS}
                />
                <FilterSelect
                  label="状态"
                  value={status}
                  onValueChange={setStatus}
                  options={STATUS_OPTIONS}
                />
              </div>
            </section>
          </div>
          <div className="flex shrink-0 items-center justify-between gap-2 border-t px-5 py-4">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="gap-1.5"
              disabled={activeFilterCount === 0}
              onClick={clearFilters}
            >
              <X className="h-4 w-4" />
              清空
            </Button>
            <Button
              type="button"
              size="sm"
              onClick={() => {
                setFiltersOpen(false)
              }}
            >
              完成
            </Button>
          </div>
        </SheetContent>
      </Sheet>

      <div
        className={`grid grid-cols-1 gap-3 md:grid-cols-2 ${isAdmin ? 'xl:grid-cols-5' : 'xl:grid-cols-4'}`}
      >
        <MetricCard title="请求" value={formatCompact(totals?.requests ?? 0)} />
        <MetricCard title="成功率" value={formatPercent(totals?.success_rate ?? 0)} />
        <MetricCard title="Token" value={formatCompact(totals?.total_tokens ?? 0)} />
        {isAdmin ? (
          <MetricCard
            title="成本"
            value={formatMoney(coalesceMoney(totals?.cost_usd), {
              currency: GATEWAY_DISPLAY_CURRENCY,
              precision: 4,
            })}
          />
        ) : null}
        <MetricCard
          title="平均延迟"
          value={`${Math.round(asNumber(totals?.avg_latency_ms)).toString()}ms`}
        />
      </div>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">
            {GROUP_OPTIONS.find((option) => option.value === groupBy)?.label ?? '维度'}排名
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {statsQuery.isLoading ? (
            <div className="px-6 py-10 text-center text-sm text-muted-foreground">加载中...</div>
          ) : null}
          {statsQuery.isError ? (
            <div className="px-6 py-10 text-center text-sm text-destructive">
              {errorMessage(statsQuery.error)}
            </div>
          ) : null}
          {!statsQuery.isLoading && !statsQuery.isError && items.length === 0 ? (
            <div className="px-6 py-10 text-center text-sm text-muted-foreground">暂无数据</div>
          ) : null}
          {!statsQuery.isLoading && !statsQuery.isError && items.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[860px] text-sm">
                <thead className="border-b bg-muted/30 text-xs uppercase text-muted-foreground">
                  <tr>
                    <th className="w-[280px] px-4 py-2 text-left font-medium">维度</th>
                    <th className="px-4 py-2 text-left font-medium">请求</th>
                    <th className="px-4 py-2 text-right font-medium">成功率</th>
                    <th className="px-4 py-2 text-right font-medium">Tokens</th>
                    {isAdmin ? <th className="px-4 py-2 text-right font-medium">成本</th> : null}
                    <th className="px-4 py-2 text-right font-medium">缓存</th>
                    <th className="px-4 py-2 text-right font-medium">延迟</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => (
                    <StatsRow
                      key={`${item.group_key}-${item.label}`}
                      item={item}
                      maxRequests={maxRequests}
                      showCost={isAdmin}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  )
}

function FilterSelect({
  label,
  value,
  onValueChange,
  onRequestOptions,
  options,
}: Readonly<{
  label: string
  value: string
  onValueChange: (value: string) => void
  onRequestOptions?: () => void
  options: SelectOption[]
}>): React.JSX.Element {
  return (
    <label className="space-y-1 text-xs font-medium text-muted-foreground">
      <span>{label}</span>
      <Select
        value={value}
        onValueChange={onValueChange}
        onOpenChange={(open) => {
          if (open) onRequestOptions?.()
        }}
      >
        <SelectTrigger className="h-9 text-xs">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL_VALUE}>全部</SelectItem>
          {options.map((option) => (
            <SelectItem key={option.value} value={option.value}>
              <span className="flex min-w-0 flex-col">
                <span className="truncate">{option.label}</span>
                {option.meta ? (
                  <span className="truncate text-[11px] text-muted-foreground">{option.meta}</span>
                ) : null}
              </span>
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </label>
  )
}

function MetricCard({
  title,
  value,
}: Readonly<{
  title: string
  value: string
}>): React.JSX.Element {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-xs font-medium text-muted-foreground">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-semibold tabular-nums">{value}</div>
      </CardContent>
    </Card>
  )
}

const StatsRow = memo(function StatsRow({
  item,
  maxRequests,
  showCost,
}: Readonly<{
  item: GatewayUsageStatsItem
  maxRequests: number
  showCost: boolean
}>): React.JSX.Element {
  const width = Math.max(4, (item.requests / maxRequests) * 100)
  return (
    <tr className="cv-auto-row border-b last:border-0 hover:bg-muted/20">
      <td className="px-4 py-3">
        <div className="min-w-0">
          <div className="truncate font-medium" title={item.label}>
            {item.label}
          </div>
          {item.group_key ? (
            <div className="truncate font-mono text-[10px] text-muted-foreground">
              {item.group_key}
            </div>
          ) : null}
        </div>
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
          {formatMoney(coalesceMoney(item.cost_usd), {
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
