/**
 * AI Gateway · 调用统计
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type React from 'react'

import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'

import { ApiError } from '@/api/errors'
import type { GatewayUsageAggregation } from '@/api/gateway/logs'
import {
  statsApi,
  type GatewayUsageStatsGroupBy,
  type GatewayUsageStatsItem,
  type GatewayUsageStatsQuery,
} from '@/api/gateway/stats'
import { teamsApi } from '@/api/gateway/teams'
import { PaginationControls } from '@/components/pagination-controls'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { budgetsAdminHref } from '@/features/gateway-budget/paths'
import { useInfiniteGatewayModelPages } from '@/features/gateway-models/hooks/use-infinite-gateway-model-pages'
import { GATEWAY_DISPLAY_CURRENCY } from '@/features/gateway-pricing/display-currency'
import { GatewayRefreshButton } from '@/features/gateway-shared/gateway-refresh-button'
import { GatewayTeamCombobox } from '@/features/gateway-teams/gateway-team-combobox'
import { gatewayTeamDisplayLabel } from '@/features/gateway-teams/gateway-team-display'
import {
  GATEWAY_FILTER_ALL,
  GatewayFilterCombobox,
  type GatewayFilterOption,
} from '@/features/gateway-usage/gateway-filter-combobox'
import {
  gatewayUsageAggregationOptions,
  isCrossTeamUsageStatsEnabled,
  usageAggregationScopeLabel,
} from '@/features/gateway-usage/usage-aggregation'
import { UsageAggregationToggle } from '@/features/gateway-usage/usage-aggregation-toggle'
import { UsageStatsCubeTable } from '@/features/gateway-usage/usage-stats-cube-table'
import { UsageStatsDetailSheet } from '@/features/gateway-usage/usage-stats-detail-sheet'
import {
  applyDrillSegmentToFilterState,
  clearDrillSegmentsFromFilterState,
  drillDownNextState,
  shouldShowBreakdownColumns,
  type StatsFilterKey,
  type UsageStatsDrillSegment,
  type UsageStatsFilterState,
} from '@/features/gateway-usage/usage-stats-drill-down'
import {
  getUsageStatsIdentityColumnHeaders,
  USAGE_STATS_GROUP_OPTIONS,
} from '@/features/gateway-usage/usage-stats-group-options'
import { UsageStatsRankingTable } from '@/features/gateway-usage/usage-stats-ranking-table'
import { usePlatformUserStatsFilterSearch } from '@/features/gateway-usage/use-platform-user-stats-filter-search'
import {
  TABLE_CREDENTIAL_TOP_N,
  useUsageStatsBreakdownBatch,
  type UsageStatsBreakdownBaseQuery,
} from '@/features/gateway-usage/use-usage-stats-breakdown-batch'
import { useUsageStatsFilterCatalog } from '@/features/gateway-usage/use-usage-stats-filter-catalog'
import { useUsageStatsProviderFilterOptions } from '@/features/gateway-usage/use-usage-stats-provider-filter-options'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useGatewayTeamId } from '@/hooks/use-gateway-team-id'
import { ChevronRight, LineChart, X } from '@/lib/lucide-icons'
import { coalesceMoney, formatMoney } from '@/lib/money'
import { DEFAULT_PAGE_SIZE, buildFilterKey, usePaginationPageForFilters } from '@/lib/pagination'
import { useUserStore } from '@/stores/user'
const PAGE_SIZE = DEFAULT_PAGE_SIZE

/** 统计页筛选触发器：略宽于旧版 9rem，下拉面板独立加宽（见 GatewayFilterCombobox） */
const STATS_FILTER_TRIGGER = 'h-9 min-w-[5.5rem] max-w-[11rem] shrink-0'
const STATS_FILTER_TRIGGER_WIDE = 'h-9 min-w-[6.5rem] max-w-[14rem] shrink-0'

const EMPTY_STATS_ITEMS: GatewayUsageStatsItem[] = []

const RANGE_DAYS: { value: 1 | 7 | 30 | 90; label: string }[] = [
  { value: 1, label: '24 小时' },
  { value: 7, label: '7 天' },
  { value: 30, label: '30 天' },
  { value: 90, label: '90 天' },
]

const STATUS_OPTIONS: GatewayFilterOption[] = [
  { value: 'success', label: '成功' },
  { value: 'failed', label: '失败' },
  { value: 'rate_limited', label: '限流' },
  { value: 'budget_exceeded', label: '预算超限' },
  { value: 'guardrail_blocked', label: '安全拦截' },
]

const CAPABILITY_OPTIONS: GatewayFilterOption[] = [
  { value: 'chat', label: 'Chat' },
  { value: 'embedding', label: 'Embedding' },
  { value: 'image', label: 'Image' },
  { value: 'audio_transcription', label: 'Audio STT' },
  { value: 'audio_speech', label: 'Audio TTS' },
  { value: 'rerank', label: 'Rerank' },
]

const INITIAL_FILTER_STATE: UsageStatsFilterState = {
  credentialId: GATEWAY_FILTER_ALL,
  userId: GATEWAY_FILTER_ALL,
  teamFilterId: GATEWAY_FILTER_ALL,
  model: GATEWAY_FILTER_ALL,
  provider: GATEWAY_FILTER_ALL,
  capability: GATEWAY_FILTER_ALL,
  status: GATEWAY_FILTER_ALL,
  vkeyId: GATEWAY_FILTER_ALL,
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

function usageStatsErrorMessage(error: unknown, aggregation: GatewayUsageAggregation): string {
  if (error instanceof ApiError) {
    if (aggregation === 'platform' && (error.status === 403 || error.status === 422)) {
      return '全平台统计需要已部署支持 usage_aggregation=platform 的后端，且当前账号须为平台管理员（role=admin）。请重启或部署 backend 后重试。'
    }
    return error.message
  }
  if (error instanceof Error) return error.message
  return '加载失败'
}

function resettable(value: string): string | undefined {
  return value === GATEWAY_FILTER_ALL ? undefined : value
}

function selectedOptionLabel(options: GatewayFilterOption[], value: string): string {
  if (value === GATEWAY_FILTER_ALL) return ''
  return options.find((option) => option.value === value)?.label ?? value
}

function filterStateToQueryParams(
  state: UsageStatsFilterState,
  crossTeamStatsEnabled: boolean
): Pick<
  GatewayUsageStatsQuery,
  | 'credential_id'
  | 'user_id'
  | 'filter_team_id'
  | 'model'
  | 'provider'
  | 'capability'
  | 'status'
  | 'vkey_id'
> {
  return {
    credential_id: resettable(state.credentialId),
    user_id: resettable(state.userId),
    filter_team_id: crossTeamStatsEnabled ? resettable(state.teamFilterId) : undefined,
    model: resettable(state.model),
    provider: resettable(state.provider),
    capability: resettable(state.capability),
    status: resettable(state.status),
    vkey_id: resettable(state.vkeyId),
  }
}

function buildLogsNavigationState(
  usageAggregation: GatewayUsageAggregation,
  state: UsageStatsFilterState,
  crossTeamStatsEnabled: boolean
): Record<string, string | undefined> {
  const q = filterStateToQueryParams(state, crossTeamStatsEnabled)
  return {
    usageAggregation,
    status: q.status,
    capability: q.capability,
    credentialId: q.credential_id,
    userId: q.user_id,
    model: q.model,
    provider: q.provider,
    vkeyId: q.vkey_id,
    teamId: q.filter_team_id,
  }
}

function buildUsageStatsQueryKey(
  teamId: string,
  days: number,
  usageAggregation: GatewayUsageAggregation,
  groupBy: GatewayUsageStatsGroupBy,
  page: number,
  filterState: UsageStatsFilterState,
  drillSegments: UsageStatsDrillSegment[]
): (string | number)[] {
  return [
    'gateway',
    'usage-stats',
    teamId,
    days,
    usageAggregation,
    groupBy,
    page,
    filterState.credentialId,
    filterState.userId,
    filterState.teamFilterId,
    filterState.model,
    filterState.provider,
    filterState.capability,
    filterState.status,
    filterState.vkeyId,
    drillSegments.map((s) => `${s.filterKey}:${s.filterValue}`).join('|'),
  ]
}

export default function GatewayStatsPage(): React.JSX.Element {
  const teamId = useGatewayTeamId()
  const { isAdmin, isPlatformAdmin } = useGatewayPermission()
  const viewerUserId = useUserStore((s) => s.currentUser?.id ?? null)
  const aggregationOptions = useMemo(
    () => gatewayUsageAggregationOptions(isPlatformAdmin),
    [isPlatformAdmin]
  )
  const tableAnchorRef = useRef<HTMLDivElement>(null)

  const [days, setDays] = useState<1 | 7 | 30 | 90>(7)
  const [usageAggregation, setUsageAggregation] = useState<GatewayUsageAggregation>('workspace')
  const platformAggBootstrapped = useRef(false)
  const [groupBy, setGroupBy] = useState<GatewayUsageStatsGroupBy>('credential')
  const [filterState, setFilterState] = useState<UsageStatsFilterState>(INITIAL_FILTER_STATE)
  const [drillSegments, setDrillSegments] = useState<UsageStatsDrillSegment[]>([])
  const [detailItem, setDetailItem] = useState<GatewayUsageStatsItem | null>(null)
  const [detailOpen, setDetailOpen] = useState(false)

  const crossTeamStatsEnabled = isCrossTeamUsageStatsEnabled(usageAggregation)

  const filterCatalog = useUsageStatsFilterCatalog({
    teamId,
    usageAggregation,
    isPlatformAdmin,
    crossTeamStatsEnabled,
  })

  const { onPickerOpenChange: onModelPickerOpenChange, ensureModelName } =
    useInfiniteGatewayModelPages(
      teamId,
      { registry_scope: 'callable' },
      { enabled: !crossTeamStatsEnabled, prefetchMode: 'open' }
    )

  useEffect(() => {
    if (crossTeamStatsEnabled || filterState.model === GATEWAY_FILTER_ALL) return
    ensureModelName(filterState.model)
  }, [crossTeamStatsEnabled, filterState.model, ensureModelName])

  useEffect(() => {
    if (!isPlatformAdmin || platformAggBootstrapped.current) return
    platformAggBootstrapped.current = true
    setUsageAggregation('platform')
  }, [isPlatformAdmin])

  const statsFilterKey = useMemo(
    () =>
      buildFilterKey([
        days,
        usageAggregation,
        groupBy,
        filterState.credentialId,
        filterState.userId,
        filterState.teamFilterId,
        filterState.model,
        filterState.provider,
        filterState.capability,
        filterState.status,
        filterState.vkeyId,
        drillSegments.map((s) => `${s.filterKey}:${s.filterValue}`).join('|'),
      ]),
    [days, usageAggregation, groupBy, filterState, drillSegments]
  )
  const [page, setPage] = usePaginationPageForFilters(statsFilterKey)

  const setFilterField = useCallback(
    <K extends keyof UsageStatsFilterState>(key: K, value: UsageStatsFilterState[K]): void => {
      setFilterState((prev) => ({ ...prev, [key]: value }))
      setPage(1)
    },
    [setPage]
  )

  useEffect(() => {
    if (crossTeamStatsEnabled) return
    setFilterField('teamFilterId', GATEWAY_FILTER_ALL)
    setGroupBy((current) => (current === 'team' ? 'credential' : current))
  }, [crossTeamStatsEnabled, setFilterField])

  const groupOptions = useMemo(
    () =>
      crossTeamStatsEnabled
        ? USAGE_STATS_GROUP_OPTIONS
        : USAGE_STATS_GROUP_OPTIONS.filter((option) => option.value !== 'team'),
    [crossTeamStatsEnabled]
  )

  const teamsQuery = useQuery({
    queryKey: ['gateway', 'teams'],
    queryFn: () => teamsApi.listTeams(),
    enabled: crossTeamStatsEnabled,
  })

  const {
    showMemberFilter,
    usePlatformUserDirectory,
    credentialOptions,
    memberOptions: teamMemberOptions,
    modelOptions,
    registryProviderOptions,
    keyOptions,
    credentialsLoading,
    membersLoading: teamMembersLoading,
    modelsLoading,
    keysLoading,
  } = filterCatalog

  const platformMemberFilter = usePlatformUserStatsFilterSearch({
    selectedUserId: filterState.userId,
    enabled: showMemberFilter && usePlatformUserDirectory,
  })

  const memberOptions = usePlatformUserDirectory ? platformMemberFilter.options : teamMemberOptions
  const membersLoading = usePlatformUserDirectory
    ? platformMemberFilter.resolvingSelection
    : teamMembersLoading

  const teamOptions = useMemo(() => teamsQuery.data ?? [], [teamsQuery.data])

  const filterQueryFields = useMemo(
    () => filterStateToQueryParams(filterState, crossTeamStatsEnabled),
    [filterState, crossTeamStatsEnabled]
  )

  const providerDiscoveryFilters = useMemo(() => {
    const { provider: _provider, ...rest } = filterQueryFields
    return rest
  }, [filterQueryFields])

  const { options: providerOptions, loading: providerOptionsLoading } =
    useUsageStatsProviderFilterOptions({
      teamId,
      days,
      usageAggregation,
      baseFilters: providerDiscoveryFilters,
      registryProviders: registryProviderOptions,
      enabled: !!teamId,
    })

  const queryParams = useMemo((): GatewayUsageStatsQuery => {
    return {
      days,
      usage_aggregation: usageAggregation,
      group_by: groupBy,
      ...filterQueryFields,
      page,
      page_size: PAGE_SIZE,
    }
  }, [days, usageAggregation, groupBy, filterQueryFields, page])

  const breakdownBaseQuery = useMemo((): UsageStatsBreakdownBaseQuery => {
    return {
      days,
      usage_aggregation: usageAggregation,
      ...filterQueryFields,
    }
  }, [days, usageAggregation, filterQueryFields])

  const statsQuery = useQuery({
    queryKey: buildUsageStatsQueryKey(
      teamId,
      days,
      usageAggregation,
      groupBy,
      page,
      filterState,
      drillSegments
    ),
    queryFn: () => statsApi.usageStats(teamId, queryParams),
    enabled: !!teamId,
  })

  const showBreakdownCols = shouldShowBreakdownColumns(groupBy)
  const identityColumnHeaders = useMemo(
    () => getUsageStatsIdentityColumnHeaders(groupBy),
    [groupBy]
  )

  const items = useMemo(() => statsQuery.data?.items ?? EMPTY_STATS_ITEMS, [statsQuery.data?.items])

  const tableCredentialTopN = useMemo(() => {
    const credentialCount = credentialOptions.length || TABLE_CREDENTIAL_TOP_N
    return Math.min(Math.max(1, credentialCount), TABLE_CREDENTIAL_TOP_N)
  }, [credentialOptions.length])

  const breakdownEnabled = showBreakdownCols && items.length > 0 && statsQuery.data !== undefined

  const { breakdownByRowKey, loadingRowKeys } = useUsageStatsBreakdownBatch({
    teamId,
    baseQuery: breakdownBaseQuery,
    parentGroupBy: groupBy,
    items,
    enabled: breakdownEnabled,
    credentialTopN: tableCredentialTopN,
  })

  const activeFilters = useMemo(
    () =>
      [
        {
          key: 'credential' as const,
          filterKey: 'credential_id' as StatsFilterKey,
          label: '凭据',
          value: selectedOptionLabel(credentialOptions, filterState.credentialId),
          clear: () => {
            setFilterField('credentialId', GATEWAY_FILTER_ALL)
          },
        },
        ...(showMemberFilter
          ? [
              {
                key: 'user' as const,
                filterKey: 'user_id' as StatsFilterKey,
                label: '人员',
                value: selectedOptionLabel(memberOptions, filterState.userId),
                clear: () => {
                  setFilterField('userId', GATEWAY_FILTER_ALL)
                },
              },
            ]
          : []),
        ...(crossTeamStatsEnabled
          ? [
              {
                key: 'team' as const,
                filterKey: 'filter_team_id' as StatsFilterKey,
                label: '团队',
                value: (() => {
                  const team = teamOptions.find((t) => t.id === filterState.teamFilterId)
                  return team
                    ? gatewayTeamDisplayLabel(team, { viewerUserId })
                    : filterState.teamFilterId
                })(),
                clear: () => {
                  setFilterField('teamFilterId', GATEWAY_FILTER_ALL)
                },
              },
            ]
          : []),
        {
          key: 'model' as const,
          filterKey: 'model' as StatsFilterKey,
          label: '模型',
          value: selectedOptionLabel(modelOptions, filterState.model),
          clear: () => {
            setFilterField('model', GATEWAY_FILTER_ALL)
          },
        },
        {
          key: 'vkey' as const,
          filterKey: 'vkey_id' as StatsFilterKey,
          label: '虚拟 Key',
          value: selectedOptionLabel(keyOptions, filterState.vkeyId),
          clear: () => {
            setFilterField('vkeyId', GATEWAY_FILTER_ALL)
          },
        },
        {
          key: 'provider' as const,
          filterKey: 'provider' as StatsFilterKey,
          label: '提供商',
          value: selectedOptionLabel(providerOptions, filterState.provider),
          clear: () => {
            setFilterField('provider', GATEWAY_FILTER_ALL)
          },
        },
        {
          key: 'capability' as const,
          filterKey: 'capability' as StatsFilterKey,
          label: '能力',
          value: selectedOptionLabel(CAPABILITY_OPTIONS, filterState.capability),
          clear: () => {
            setFilterField('capability', GATEWAY_FILTER_ALL)
          },
        },
        {
          key: 'status' as const,
          filterKey: 'status' as StatsFilterKey,
          label: '状态',
          value: selectedOptionLabel(STATUS_OPTIONS, filterState.status),
          clear: () => {
            setFilterField('status', GATEWAY_FILTER_ALL)
          },
        },
      ].filter((filter) => filter.value.length > 0 && filter.value !== GATEWAY_FILTER_ALL),
    [
      credentialOptions,
      filterState.credentialId,
      filterState.userId,
      filterState.teamFilterId,
      filterState.model,
      filterState.vkeyId,
      filterState.provider,
      filterState.capability,
      filterState.status,
      memberOptions,
      showMemberFilter,
      crossTeamStatsEnabled,
      teamOptions,
      viewerUserId,
      modelOptions,
      keyOptions,
      providerOptions,
      setFilterField,
    ]
  )

  const activeFilterCount = activeFilters.length

  const clearManualFilters = useCallback((): void => {
    setFilterState(clearDrillSegmentsFromFilterState(INITIAL_FILTER_STATE, drillSegments))
  }, [drillSegments])

  const resetDrillToRoot = useCallback((): void => {
    setDrillSegments([])
    setFilterState(clearDrillSegmentsFromFilterState(filterState, drillSegments))
    setGroupBy('credential')
    setPage(1)
  }, [drillSegments, filterState, setPage])

  const popDrillToIndex = useCallback(
    (index: number): void => {
      const kept = drillSegments.slice(0, index + 1)
      const removed = drillSegments.slice(index + 1)
      let nextState = clearDrillSegmentsFromFilterState(INITIAL_FILTER_STATE, removed)
      for (const segment of kept) {
        nextState = applyDrillSegmentToFilterState(nextState, segment)
      }
      setDrillSegments(kept)
      setFilterState(nextState)
      const lastSegment = kept.at(-1)
      setGroupBy(lastSegment !== undefined ? lastSegment.groupByAfter : 'credential')
      setPage(1)
    },
    [drillSegments, setPage]
  )

  const handleRowDrill = useCallback(
    (item: GatewayUsageStatsItem): void => {
      const next = drillDownNextState(groupBy, item.group_key, item.label)
      if (next === null) return
      setDrillSegments((prev) => [...prev, next.segment])
      setFilterState((prev) => applyDrillSegmentToFilterState(prev, next.segment))
      setGroupBy(next.groupBy)
      setPage(1)
      tableAnchorRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    },
    [groupBy, setPage]
  )

  const maxRequests = useMemo(() => Math.max(...items.map((item) => item.requests), 1), [items])

  const handleShowDetail = useCallback((row: GatewayUsageStatsItem): void => {
    setDetailItem(row)
    setDetailOpen(true)
  }, [])

  const navigate = useNavigate()

  const handleSetQuota = useCallback(
    (item: GatewayUsageStatsItem): void => {
      const params: { layer?: string; model?: string; credential?: string; user?: string } = {}
      if (groupBy === 'model') params.model = item.group_key
      else if (groupBy === 'user') params.user = item.group_key
      else if (groupBy === 'credential') params.credential = item.group_key
      navigate(budgetsAdminHref(teamId, params))
    },
    [groupBy, navigate, teamId]
  )

  const totals = statsQuery.data?.totals

  const logsNavigationState = useMemo(
    () => buildLogsNavigationState(usageAggregation, filterState, crossTeamStatsEnabled),
    [usageAggregation, filterState, crossTeamStatsEnabled]
  )

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
              ? `${new Date(statsQuery.data.start).toLocaleDateString()} - ${new Date(statsQuery.data.end).toLocaleDateString()} · ${usageAggregationScopeLabel(usageAggregation)}`
              : `${usageAggregationScopeLabel(usageAggregation)} · 按当前时间窗口聚合调用日志`}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <UsageAggregationToggle
            value={usageAggregation}
            onChange={setUsageAggregation}
            options={aggregationOptions}
          />
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
          <div className="hidden h-6 w-px bg-border sm:block" />
          <div className="flex flex-wrap gap-1">
            {groupOptions.map((option) => (
              <Button
                key={option.value}
                type="button"
                size="sm"
                variant={groupBy === option.value ? 'default' : 'ghost'}
                className="h-7 px-2.5 text-xs"
                onClick={() => {
                  setGroupBy(option.value)
                }}
              >
                {option.label}
              </Button>
            ))}
          </div>
          <GatewayRefreshButton
            isFetching={statsQuery.isFetching}
            ariaLabel="刷新统计"
            onRefresh={() => statsQuery.refetch()}
          />
        </div>
      </div>

      <div
        className={`grid grid-cols-1 gap-3 md:grid-cols-2 ${isAdmin ? 'xl:grid-cols-6' : 'xl:grid-cols-5'}`}
      >
        <MetricCard title="请求" value={formatCompact(totals?.requests ?? 0)} />
        <MetricCard title="成功率" value={formatPercent(totals?.success_rate ?? 0)} />
        <MetricCard title="Token" value={formatCompact(totals?.total_tokens ?? 0)} />
        <MetricCard title="缓存命中" value={formatPercent(totals?.cache_hit_rate ?? 0)} />
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

      <Card ref={tableAnchorRef}>
        <CardHeader className="space-y-3 pb-3">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
            <CardTitle className="pt-1 text-base">
              {groupOptions.find((option) => option.value === groupBy)?.label ?? '维度'}排名
            </CardTitle>
            <div
              className="flex flex-wrap items-center gap-2.5"
              role="group"
              aria-label="调用统计筛选"
            >
              <GatewayFilterCombobox
                value={filterState.credentialId}
                onChange={(v) => {
                  setFilterField('credentialId', v)
                }}
                options={credentialOptions}
                placeholder="凭据"
                searchPlaceholder="搜索凭据…"
                menuWidth="wide"
                loading={credentialsLoading}
                active={filterState.credentialId !== GATEWAY_FILTER_ALL}
                className={STATS_FILTER_TRIGGER_WIDE}
              />
              {showMemberFilter ? (
                <GatewayFilterCombobox
                  value={filterState.userId}
                  onChange={(v) => {
                    setFilterField('userId', v)
                  }}
                  options={memberOptions}
                  placeholder="人员"
                  searchPlaceholder={usePlatformUserDirectory ? '姓名或邮箱…' : '搜索人员…'}
                  searchMode={usePlatformUserDirectory ? 'server' : 'client'}
                  onSearchQueryChange={
                    usePlatformUserDirectory ? platformMemberFilter.onSearchQueryChange : undefined
                  }
                  onOpenChange={
                    usePlatformUserDirectory ? platformMemberFilter.onPickerOpenChange : undefined
                  }
                  remoteSearching={
                    usePlatformUserDirectory ? platformMemberFilter.remoteSearching : false
                  }
                  emptyHint={
                    usePlatformUserDirectory
                      ? '输入姓名或邮箱搜索；无关键词时仅显示前 40 名活跃用户'
                      : undefined
                  }
                  loading={membersLoading}
                  active={filterState.userId !== GATEWAY_FILTER_ALL}
                  menuWidth="wide"
                  className={STATS_FILTER_TRIGGER_WIDE}
                />
              ) : null}
              <GatewayFilterCombobox
                value={filterState.model}
                onChange={(v) => {
                  setFilterField('model', v)
                }}
                options={modelOptions}
                placeholder="模型"
                searchPlaceholder="搜索模型…"
                menuWidth="wide"
                optionLayout="multiline"
                loading={modelsLoading}
                onOpenChange={(open) => {
                  if (open && !crossTeamStatsEnabled) onModelPickerOpenChange(true)
                }}
                active={filterState.model !== GATEWAY_FILTER_ALL}
                className={STATS_FILTER_TRIGGER_WIDE}
              />
              <GatewayFilterCombobox
                value={filterState.provider}
                onChange={(v) => {
                  setFilterField('provider', v)
                }}
                options={providerOptions}
                placeholder="提供商"
                searchPlaceholder="搜索提供商…"
                loading={providerOptionsLoading}
                active={filterState.provider !== GATEWAY_FILTER_ALL}
                className={STATS_FILTER_TRIGGER}
              />
              <GatewayFilterCombobox
                value={filterState.status}
                onChange={(v) => {
                  setFilterField('status', v)
                }}
                options={STATUS_OPTIONS}
                placeholder="状态"
                searchPlaceholder="搜索状态…"
                active={filterState.status !== GATEWAY_FILTER_ALL}
                className={STATS_FILTER_TRIGGER}
              />
              <GatewayFilterCombobox
                value={filterState.capability}
                onChange={(v) => {
                  setFilterField('capability', v)
                }}
                options={CAPABILITY_OPTIONS}
                placeholder="能力"
                searchPlaceholder="搜索能力…"
                active={filterState.capability !== GATEWAY_FILTER_ALL}
                className={STATS_FILTER_TRIGGER}
              />
              <GatewayFilterCombobox
                value={filterState.vkeyId}
                onChange={(v) => {
                  setFilterField('vkeyId', v)
                }}
                options={keyOptions}
                placeholder="虚拟 Key"
                searchPlaceholder="搜索 Key…"
                menuWidth="wide"
                loading={keysLoading}
                active={filterState.vkeyId !== GATEWAY_FILTER_ALL}
                className={STATS_FILTER_TRIGGER_WIDE}
              />
              {crossTeamStatsEnabled ? (
                <GatewayTeamCombobox
                  allowAll
                  allLabel="全部团队"
                  value={filterState.teamFilterId}
                  onChange={(teamFilterId) => {
                    setFilterField('teamFilterId', teamFilterId)
                  }}
                  teams={teamOptions}
                  placeholder="全部团队"
                  className={STATS_FILTER_TRIGGER_WIDE}
                  popoverContentClassName="min-w-[min(18rem,calc(100vw-1.5rem))] max-w-[min(28rem,calc(100vw-1.5rem))]"
                  active={filterState.teamFilterId !== GATEWAY_FILTER_ALL}
                />
              ) : null}
            </div>
          </div>
          {(drillSegments.length > 0 || activeFilterCount > 0) && (
            <div className="flex flex-wrap items-center gap-2 text-xs">
              {drillSegments.length > 0 ? (
                <nav aria-label="钻取路径" className="flex flex-wrap items-center gap-1">
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-7 px-2"
                    onClick={resetDrillToRoot}
                  >
                    全部
                  </Button>
                  {drillSegments.map((segment, index) => (
                    <span
                      key={`${segment.filterKey}-${segment.filterValue}`}
                      className="flex items-center gap-1"
                    >
                      <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" aria-hidden />
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-7 max-w-[200px] truncate px-2"
                        title={segment.label}
                        onClick={() => {
                          popDrillToIndex(index)
                        }}
                      >
                        {segment.label}
                      </Button>
                    </span>
                  ))}
                </nav>
              ) : null}
              {activeFilterCount > 0 ? (
                <div className="flex flex-wrap gap-1.5">
                  {activeFilters.map((filter) => (
                    <Badge
                      key={filter.key}
                      variant="outline"
                      className="max-w-[240px] gap-1 truncate font-normal"
                    >
                      <span className="text-muted-foreground">{filter.label}</span>
                      <span className="truncate">{filter.value}</span>
                      <button
                        type="button"
                        className="rounded-sm hover:bg-muted"
                        aria-label={`移除${filter.label}筛选`}
                        onClick={filter.clear}
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </Badge>
                  ))}
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-7 gap-1 px-2"
                    onClick={clearManualFilters}
                  >
                    清空筛选
                  </Button>
                </div>
              ) : null}
            </div>
          )}
        </CardHeader>
        <CardContent className="p-0">
          {statsQuery.isLoading ? (
            <div className="px-6 py-10 text-center text-sm text-muted-foreground">加载中...</div>
          ) : null}
          {statsQuery.isError ? (
            <div className="px-6 py-10 text-center text-sm text-destructive">
              {usageStatsErrorMessage(statsQuery.error, usageAggregation)}
            </div>
          ) : null}
          {!statsQuery.isLoading && !statsQuery.isError && items.length === 0 ? (
            <div className="px-6 py-10 text-center text-sm text-muted-foreground">暂无数据</div>
          ) : null}
          {!statsQuery.isLoading && !statsQuery.isError && items.length > 0 ? (
            groupBy === 'user_model_credential' ? (
              <UsageStatsCubeTable items={items} maxRequests={maxRequests} showCost={isAdmin} />
            ) : (
              <UsageStatsRankingTable
                items={items}
                maxRequests={maxRequests}
                showCost={isAdmin}
                showBreakdownCols={showBreakdownCols}
                identityColumnHeaders={identityColumnHeaders}
                breakdownByRowKey={breakdownByRowKey}
                loadingRowKeys={loadingRowKeys}
                credentialTopN={tableCredentialTopN}
                onDrill={handleRowDrill}
                onShowDetail={handleShowDetail}
                onSetQuota={handleSetQuota}
              />
            )
          ) : null}
          {statsQuery.data && statsQuery.data.total > PAGE_SIZE ? (
            <div className="border-t px-4 py-3">
              <PaginationControls
                page={statsQuery.data.page}
                page_size={statsQuery.data.page_size}
                total={statsQuery.data.total}
                has_next={statsQuery.data.has_next}
                has_prev={statsQuery.data.has_prev}
                onPageChange={setPage}
              />
            </div>
          ) : null}
        </CardContent>
      </Card>

      <UsageStatsDetailSheet
        open={detailOpen}
        onOpenChange={setDetailOpen}
        teamId={teamId}
        groupBy={groupBy}
        item={detailItem}
        baseQuery={breakdownBaseQuery}
        sheetOpen={detailOpen}
        logsNavigationState={logsNavigationState}
      />
    </div>
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
