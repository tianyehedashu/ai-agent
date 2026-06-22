/**
 * AI Gateway · 调用日志
 */

import type { ReactNode } from 'react'
import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useVirtualizer, type VirtualItem } from '@tanstack/react-virtual'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'

import {
  gatewayApi,
  type GatewayLogDetail,
  type GatewayLogItem,
  type GatewayUsageAggregation,
} from '@/api/gateway'
import { PaginationControls } from '@/components/pagination-controls'
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
import { GATEWAY_CLIENT_TYPES, type GatewayClientType } from '@/features/gateway-usage/client-types'
import {
  credentialDisplayText,
  credentialDisplayTitle,
} from '@/features/gateway-usage/credential-display'
import {
  GATEWAY_FILTER_ALL,
  GatewayFilterCombobox,
} from '@/features/gateway-usage/gateway-filter-combobox'
import {
  logCallerDisplayText,
  logCallerDisplayTitle,
} from '@/features/gateway-usage/log-caller-display'
import { LogListResizableHeader } from '@/features/gateway-usage/log-list-resizable-header'
import {
  logModelIdentityTitle,
  resolveLogModelIdentity,
  type LogModelCatalogIndex,
  type LogModelIdentity,
} from '@/features/gateway-usage/log-model-identity'
import { LogPricingBreakdown } from '@/features/gateway-usage/log-pricing-breakdown'
import {
  gatewayUsageAggregationOptions,
  usageAggregationScopeLabel,
} from '@/features/gateway-usage/usage-aggregation'
import { UsageAggregationToggle } from '@/features/gateway-usage/usage-aggregation-toggle'
import { usageLogsShowCaller } from '@/features/gateway-usage/usage-stats-filter-catalog'
import { useLogFilterCatalog } from '@/features/gateway-usage/use-log-filter-catalog'
import { useLogListColumnWidths } from '@/features/gateway-usage/use-log-list-column-widths'
import { usePlatformUserStatsFilterSearch } from '@/features/gateway-usage/use-platform-user-stats-filter-search'
import { useTeamMemberFilterSearch } from '@/features/gateway-usage/use-team-member-filter-search'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useGatewayTeamId, useGatewayTeamRecord } from '@/hooks/use-gateway-team-id'
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
import { cn, copyToClipboard } from '@/lib/utils'

import { resolveDateRange, isValidDateRangeValue, type DateRangeValue } from './logs-utils'

const PAGE_SIZE_OPTIONS = [50, 100, 200] as const

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

const CLIENT_TYPE_FILTERS: readonly { value: GatewayClientType | 'all'; label: string }[] = [
  { value: 'all', label: '全部来源' },
  { value: GATEWAY_CLIENT_TYPES.MODEL_CONNECTIVITY_PROBE, label: '模型探活' },
  { value: GATEWAY_CLIENT_TYPES.UNKNOWN, label: '普通调用' },
]

const DATE_RANGE_FILTERS: readonly { value: DateRangeValue; label: string }[] = [
  { value: '1h', label: '最近1小时' },
  { value: 'today', label: '今天' },
  { value: '7d', label: '最近7天' },
  { value: '30d', label: '最近30天' },
]

interface LogsLocationState {
  usageStatsFilters?: {
    usageAggregation?: GatewayUsageAggregation
    status?: string
    capability?: string
    userId?: string
    credentialId?: string
    model?: string
    vkeyId?: string
  }
}

export default function GatewayLogsPage(): React.JSX.Element {
  const teamId = useGatewayTeamId()
  const teamRecord = useGatewayTeamRecord(teamId)
  const { isPlatformAdmin } = useGatewayPermission()
  const aggregationOptions = useMemo(
    () => gatewayUsageAggregationOptions(isPlatformAdmin),
    [isPlatformAdmin]
  )
  const location = useLocation()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const parentRef = useRef<HTMLDivElement>(null)
  const consumedStatsNavigationRef = useRef(false)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [copiedRequestId, setCopiedRequestId] = useState(false)
  const [pageSize, setPageSize] = useState(() => {
    const v = Number(searchParams.get('size'))
    return PAGE_SIZE_OPTIONS.includes(v as (typeof PAGE_SIZE_OPTIONS)[number]) ? v : 100
  })
  const [page, setPage] = useState(() => {
    const v = Number(searchParams.get('page'))
    return v >= 1 ? v : 1
  })

  // 筛选状态：优先从 URL 恢复，否则用默认值
  const [statusFilter, setStatusFilter] = useState(() => {
    const v = searchParams.get('status')
    const found = STATUS_FILTERS.find((f) => f.value === v)
    return found ? found.value : 'all'
  })
  const [capabilityFilter, setCapabilityFilter] = useState(() => {
    const v = searchParams.get('capability')
    const found = CAPABILITY_FILTERS.find((f) => f.value === v)
    return found ? found.value : 'all'
  })
  const [dateRange, setDateRange] = useState<DateRangeValue>(() => {
    const v = searchParams.get('range')
    return isValidDateRangeValue(v) ? v : 'today'
  })
  const [usageAggregation, setUsageAggregation] = useState<GatewayUsageAggregation>(() => {
    const v = searchParams.get('agg') as GatewayUsageAggregation | null
    return v === 'workspace' || v === 'user' || v === 'platform' ? v : 'user'
  })
  const [userFilter, setUserFilter] = useState(() => {
    const v = searchParams.get('user')
    return v && v !== GATEWAY_FILTER_ALL ? v : GATEWAY_FILTER_ALL
  })
  const [credentialFilter, setCredentialFilter] = useState(() => {
    const v = searchParams.get('credential')
    return v && v !== GATEWAY_FILTER_ALL ? v : GATEWAY_FILTER_ALL
  })
  const [vkeyFilter, setVkeyFilter] = useState(() => {
    const v = searchParams.get('vkey')
    return v && v !== GATEWAY_FILTER_ALL ? v : GATEWAY_FILTER_ALL
  })
  const [modelFilter, setModelFilter] = useState(() => {
    const v = searchParams.get('model')
    return v && v !== GATEWAY_FILTER_ALL ? v : GATEWAY_FILTER_ALL
  })
  const [clientTypeFilter, setClientTypeFilter] = useState<GatewayClientType | 'all'>(() => {
    const v = searchParams.get('client_type')
    const found = CLIENT_TYPE_FILTERS.find((f) => f.value === v)
    return found ? found.value : 'all'
  })

  // 筛选目录数据
  const { credentialOptions, keyOptions, modelOptions, modelCatalogIndex } = useLogFilterCatalog({
    teamId,
  })

  // 调用人列 / 人员筛选：全平台始终显示；团队 workspace 在个人团队下隐藏
  const isPersonalTeam = teamRecord?.kind === 'personal'
  const showCallerColumn = usageLogsShowCaller(usageAggregation, isPersonalTeam)
  const usePlatformUserDirectory =
    showCallerColumn && usageAggregation === 'platform' && isPlatformAdmin
  const teamMemberFilter = useTeamMemberFilterSearch({
    teamId,
    selectedUserId: userFilter,
    enabled: showCallerColumn && !usePlatformUserDirectory,
  })
  const platformMemberFilter = usePlatformUserStatsFilterSearch({
    selectedUserId: userFilter,
    enabled: showCallerColumn && usePlatformUserDirectory,
  })
  const callerFilterOptions = usePlatformUserDirectory
    ? platformMemberFilter.options
    : teamMemberFilter.options
  const callerFilterLoading = usePlatformUserDirectory
    ? platformMemberFilter.resolvingSelection
    : teamMemberFilter.resolvingSelection

  // URL 同步：筛选变化时更新 query params（保留非日志相关参数）
  useEffect(() => {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        const logKeys = [
          'status',
          'capability',
          'range',
          'agg',
          'user',
          'credential',
          'vkey',
          'model',
          'client_type',
          'size',
        ]
        for (const key of logKeys) {
          next.delete(key)
        }
        if (statusFilter !== 'all') next.set('status', statusFilter)
        if (capabilityFilter !== 'all') next.set('capability', capabilityFilter)
        if (dateRange !== 'today') next.set('range', dateRange)
        if (usageAggregation !== 'user') next.set('agg', usageAggregation)
        if (userFilter !== GATEWAY_FILTER_ALL) next.set('user', userFilter)
        if (credentialFilter !== GATEWAY_FILTER_ALL) next.set('credential', credentialFilter)
        if (vkeyFilter !== GATEWAY_FILTER_ALL) next.set('vkey', vkeyFilter)
        if (modelFilter !== GATEWAY_FILTER_ALL) next.set('model', modelFilter)
        if (clientTypeFilter !== 'all') next.set('client_type', clientTypeFilter)
        if (pageSize !== 100) next.set('size', String(pageSize))
        if (page > 1) next.set('page', String(page))
        return next
      },
      { replace: true }
    )
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    statusFilter,
    capabilityFilter,
    dateRange,
    usageAggregation,
    userFilter,
    credentialFilter,
    vkeyFilter,
    modelFilter,
    clientTypeFilter,
    pageSize,
    page,
  ])

  // 浏览器前进/后退：URL 外部变化时同步回组件状态
  useEffect(() => {
    const vStatus = searchParams.get('status')
    const foundStatus = STATUS_FILTERS.find((f) => f.value === vStatus)
    const nextStatus = foundStatus ? foundStatus.value : 'all'
    if (nextStatus !== statusFilter) setStatusFilter(nextStatus)

    const vCapability = searchParams.get('capability')
    const foundCapability = CAPABILITY_FILTERS.find((f) => f.value === vCapability)
    const nextCapability = foundCapability ? foundCapability.value : 'all'
    if (nextCapability !== capabilityFilter) setCapabilityFilter(nextCapability)

    const vRange = searchParams.get('range')
    const nextRange = isValidDateRangeValue(vRange) ? vRange : 'today'
    if (nextRange !== dateRange) setDateRange(nextRange)

    const vAgg = searchParams.get('agg') as GatewayUsageAggregation | null
    const nextAgg = vAgg === 'workspace' || vAgg === 'user' || vAgg === 'platform' ? vAgg : 'user'
    if (nextAgg !== usageAggregation) setUsageAggregation(nextAgg)

    const vUser = searchParams.get('user')
    const nextUser = vUser && vUser !== GATEWAY_FILTER_ALL ? vUser : GATEWAY_FILTER_ALL
    if (nextUser !== userFilter) setUserFilter(nextUser)

    const vCredential = searchParams.get('credential')
    const nextCredential =
      vCredential && vCredential !== GATEWAY_FILTER_ALL ? vCredential : GATEWAY_FILTER_ALL
    if (nextCredential !== credentialFilter) setCredentialFilter(nextCredential)

    const vVkey = searchParams.get('vkey')
    const nextVkey = vVkey && vVkey !== GATEWAY_FILTER_ALL ? vVkey : GATEWAY_FILTER_ALL
    if (nextVkey !== vkeyFilter) setVkeyFilter(nextVkey)

    const vModel = searchParams.get('model')
    const nextModel = vModel && vModel !== GATEWAY_FILTER_ALL ? vModel : GATEWAY_FILTER_ALL
    if (nextModel !== modelFilter) setModelFilter(nextModel)

    const vClientType = searchParams.get('client_type')
    const foundClientType = CLIENT_TYPE_FILTERS.find((f) => f.value === vClientType)
    const nextClientType = foundClientType ? foundClientType.value : 'all'
    if (nextClientType !== clientTypeFilter) setClientTypeFilter(nextClientType)

    const vSize = Number(searchParams.get('size'))
    const nextSize = PAGE_SIZE_OPTIONS.includes(vSize as (typeof PAGE_SIZE_OPTIONS)[number])
      ? vSize
      : 100
    if (nextSize !== pageSize) setPageSize(nextSize)

    const vPage = Number(searchParams.get('page'))
    const nextPage = vPage >= 1 ? vPage : 1
    if (nextPage !== page) setPage(nextPage)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams])

  // 从统计页导航过来的状态恢复
  useEffect(() => {
    if (consumedStatsNavigationRef.current) return
    const state = location.state as LogsLocationState | null
    const fromStats = state?.usageStatsFilters
    if (!fromStats) return
    consumedStatsNavigationRef.current = true
    if (fromStats.usageAggregation) {
      setUsageAggregation(fromStats.usageAggregation)
    }
    if (fromStats.status) {
      setStatusFilter(fromStats.status)
    }
    if (fromStats.capability) {
      setCapabilityFilter(fromStats.capability)
    }
    if (fromStats.userId) {
      setUserFilter(fromStats.userId)
    }
    if (fromStats.credentialId) {
      setCredentialFilter(fromStats.credentialId)
    }
    if (fromStats.model) {
      setModelFilter(fromStats.model)
    }
    if (fromStats.vkeyId) {
      setVkeyFilter(fromStats.vkeyId)
    }
    navigate(
      { pathname: location.pathname, search: location.search },
      { replace: true, state: null }
    )
  }, [location.pathname, location.search, location.state, navigate])

  const { start: rangeStart, end: rangeEnd } = useMemo(
    () => resolveDateRange(dateRange),
    [dateRange]
  )

  const resetListPosition = (): void => {
    setSelectedId(null)
    setPage(1)
    parentRef.current?.scrollTo({ top: 0 })
  }

  const hasFilters =
    statusFilter !== 'all' ||
    capabilityFilter !== 'all' ||
    dateRange !== 'today' ||
    (showCallerColumn && userFilter !== GATEWAY_FILTER_ALL) ||
    credentialFilter !== GATEWAY_FILTER_ALL ||
    vkeyFilter !== GATEWAY_FILTER_ALL ||
    modelFilter !== GATEWAY_FILTER_ALL ||
    clientTypeFilter !== 'all'

  const queryFilters = useMemo(
    () => ({
      usage_aggregation: usageAggregation,
      status: statusFilter === 'all' ? undefined : statusFilter,
      capability: capabilityFilter === 'all' ? undefined : capabilityFilter,
      start: rangeStart.toISOString(),
      end: rangeEnd.toISOString(),
      user_id: showCallerColumn && userFilter !== GATEWAY_FILTER_ALL ? userFilter : undefined,
      credential_id: credentialFilter === GATEWAY_FILTER_ALL ? undefined : credentialFilter,
      vkey_id: vkeyFilter === GATEWAY_FILTER_ALL ? undefined : vkeyFilter,
      model: modelFilter === GATEWAY_FILTER_ALL ? undefined : modelFilter,
      client_type: clientTypeFilter === 'all' ? undefined : clientTypeFilter,
    }),
    [
      usageAggregation,
      statusFilter,
      capabilityFilter,
      rangeStart,
      rangeEnd,
      showCallerColumn,
      userFilter,
      credentialFilter,
      vkeyFilter,
      modelFilter,
      clientTypeFilter,
    ]
  )

  const { data, isFetching, isLoading, refetch } = useQuery({
    queryKey: ['gateway', 'logs', teamId, queryFilters, pageSize, page],
    queryFn: () =>
      gatewayApi.listLogs(teamId, {
        ...queryFilters,
        page,
        page_size: pageSize,
      }),
    placeholderData: keepPreviousData,
  })

  // 汇总统计
  const { data: summary } = useQuery({
    queryKey: ['gateway', 'log-summary', teamId, queryFilters],
    queryFn: () =>
      gatewayApi.dashboard(teamId, {
        ...queryFilters,
      }),
    enabled: !!teamId,
  })

  const items = useMemo(() => data?.items ?? [], [data?.items])
  const listTotalExact = data?.total_exact !== false
  const listSubtitle = useMemo(() => {
    const scope = usageAggregationScopeLabel(usageAggregation)
    if (summary && summary.total_requests > 0) {
      return `${scope} · 筛选范围内约 ${summary.total_requests.toLocaleString()} 次请求`
    }
    if (items.length > 0) {
      return `${scope} · 本页 ${String(items.length)} 条${data?.has_next ? '（还有更多）' : ''}`
    }
    return scope
  }, [usageAggregation, summary, items.length, data?.has_next])

  const {
    gridTemplateColumns: logGridTemplateColumns,
    tableMinWidth: logTableMinWidth,
    startResize,
    resetColumn,
  } = useLogListColumnWidths({ showCallerColumn })

  const virtualizer = useVirtualizer({
    count: items.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 48,
    overscan: 8,
  })

  const virtualItems = virtualizer.getVirtualItems()

  const selectedItem = useMemo(
    () => items.find((item) => item.id === selectedId),
    [items, selectedId]
  )

  const handleRowSelect = useCallback((id: string) => {
    setSelectedId(id)
  }, [])

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

  const activeLogIdentity = useMemo(
    () => (activeLog ? resolveLogModelIdentity(activeLog, modelCatalogIndex) : null),
    [activeLog, modelCatalogIndex]
  )

  const clearFilters = (): void => {
    setStatusFilter('all')
    setCapabilityFilter('all')
    setDateRange('today')
    setUserFilter(GATEWAY_FILTER_ALL)
    setCredentialFilter(GATEWAY_FILTER_ALL)
    setVkeyFilter(GATEWAY_FILTER_ALL)
    setModelFilter(GATEWAY_FILTER_ALL)
    setClientTypeFilter('all')
    resetListPosition()
  }

  const copyRequestId = (value: string): void => {
    void copyToClipboard(value)
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
          <p className="text-sm text-muted-foreground">{listSubtitle}</p>
        </div>
        <UsageAggregationToggle
          value={usageAggregation}
          onChange={(next) => {
            setUsageAggregation(next)
            resetListPosition()
          }}
          options={aggregationOptions}
        />
      </div>

      {/* 汇总统计卡片 */}
      {summary ? (
        <div className="grid grid-cols-2 gap-2 md:grid-cols-6">
          <MetricTile
            icon={<Receipt className="h-4 w-4" />}
            label="总请求"
            value={summary.total_requests.toLocaleString()}
          />
          <MetricTile
            icon={<Zap className="h-4 w-4" />}
            label="Tokens"
            value={(summary.total_input_tokens + summary.total_output_tokens).toLocaleString()}
            caption={`${summary.total_input_tokens.toLocaleString()} in / ${summary.total_output_tokens.toLocaleString()} out`}
          />
          {(summary.total_cached_tokens > 0 || summary.total_cache_creation_tokens > 0) && (
            <MetricTile
              icon={<Database className="h-4 w-4" />}
              label="缓存"
              value={
                summary.total_cached_tokens > 0
                  ? `${summary.total_cached_tokens.toLocaleString()} 读`
                  : ''
              }
              caption={
                summary.total_cache_creation_tokens > 0
                  ? `${summary.total_cache_creation_tokens.toLocaleString()} 写`
                  : undefined
              }
            />
          )}
          <MetricTile
            icon={<Receipt className="h-4 w-4" />}
            label="成本"
            value={formatMoney(coalesceMoney(summary.total_cost_usd), {
              currency: GATEWAY_DISPLAY_CURRENCY,
              precision: 4,
            })}
          />
          <MetricTile
            icon={<CheckCircle2 className="h-4 w-4" />}
            label="成功率"
            value={`${(summary.success_rate * 100).toFixed(1)}%`}
            caption={`${summary.success_count.toLocaleString()} / ${summary.failure_count.toLocaleString()}`}
          />
          <MetricTile
            icon={<Clock className="h-4 w-4" />}
            label="平均延迟"
            value={`${Math.round(summary.avg_latency_ms).toLocaleString()}ms`}
          />
          <MetricTile
            icon={<Clock className="h-4 w-4" />}
            label="平均首字节"
            value={`${Math.round(summary.avg_ttfb_ms).toLocaleString()}ms`}
          />
        </div>
      ) : null}

      {/* 筛选栏 */}
      <div className="flex flex-col gap-2 rounded-lg border bg-background p-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-wrap items-center gap-2">
          <Select
            value={dateRange}
            onValueChange={(next) => {
              if (isValidDateRangeValue(next)) {
                setDateRange(next)
                resetListPosition()
              }
            }}
          >
            <SelectTrigger className="h-9 w-[132px]" aria-label="按时间范围筛选">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {DATE_RANGE_FILTERS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select
            value={statusFilter}
            onValueChange={(next) => {
              setStatusFilter(next)
              resetListPosition()
            }}
          >
            <SelectTrigger className="h-9 w-[120px]" aria-label="按状态筛选">
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
            <SelectTrigger className="h-9 w-[136px]" aria-label="按能力筛选">
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

          <Select
            value={clientTypeFilter}
            onValueChange={(next) => {
              const value = next as GatewayClientType | 'all'
              const found = CLIENT_TYPE_FILTERS.find((f) => f.value === value)
              if (!found) return
              setClientTypeFilter(found.value)
              resetListPosition()
            }}
          >
            <SelectTrigger className="h-9 w-[140px]" aria-label="按调用来源筛选">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {CLIENT_TYPE_FILTERS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {showCallerColumn ? (
            <GatewayFilterCombobox
              value={userFilter}
              onChange={(next) => {
                setUserFilter(next)
                resetListPosition()
              }}
              options={callerFilterOptions}
              placeholder="调用人"
              active={userFilter !== GATEWAY_FILTER_ALL}
              searchMode="server"
              searchPlaceholder={usePlatformUserDirectory ? '姓名或邮箱…' : '搜索人员…'}
              onSearchQueryChange={
                usePlatformUserDirectory
                  ? platformMemberFilter.onSearchQueryChange
                  : teamMemberFilter.onSearchQueryChange
              }
              onOpenChange={
                usePlatformUserDirectory
                  ? platformMemberFilter.onPickerOpenChange
                  : teamMemberFilter.onPickerOpenChange
              }
              remoteSearching={
                usePlatformUserDirectory
                  ? platformMemberFilter.remoteSearching
                  : teamMemberFilter.remoteSearching
              }
              loading={callerFilterLoading}
              emptyHint={
                usePlatformUserDirectory
                  ? '输入姓名或邮箱搜索；无关键词时仅显示前 40 名活跃用户'
                  : undefined
              }
            />
          ) : null}

          <GatewayFilterCombobox
            value={credentialFilter}
            onChange={(next) => {
              setCredentialFilter(next)
              resetListPosition()
            }}
            options={credentialOptions}
            placeholder="凭据"
            active={credentialFilter !== GATEWAY_FILTER_ALL}
          />

          <GatewayFilterCombobox
            value={vkeyFilter}
            onChange={(next) => {
              setVkeyFilter(next)
              resetListPosition()
            }}
            options={keyOptions}
            placeholder="虚拟 Key"
            active={vkeyFilter !== GATEWAY_FILTER_ALL}
          />

          <GatewayFilterCombobox
            value={modelFilter}
            onChange={(next) => {
              setModelFilter(next)
              resetListPosition()
            }}
            options={modelOptions}
            placeholder="模型"
            menuWidth="wide"
            active={modelFilter !== GATEWAY_FILTER_ALL}
          />
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
          <div style={{ minWidth: logTableMinWidth }}>
            <div
              className="grid border-b bg-muted/30 px-3 py-2 text-xs font-medium text-muted-foreground"
              style={{ gridTemplateColumns: logGridTemplateColumns }}
            >
              <LogListResizableHeader
                columnKey="time"
                startResize={startResize}
                resetColumn={resetColumn}
              >
                时间
              </LogListResizableHeader>
              {showCallerColumn ? (
                <LogListResizableHeader
                  columnKey="caller"
                  startResize={startResize}
                  resetColumn={resetColumn}
                >
                  调用人
                </LogListResizableHeader>
              ) : null}
              <LogListResizableHeader
                columnKey="invokeName"
                startResize={startResize}
                resetColumn={resetColumn}
              >
                调用名
              </LogListResizableHeader>
              <LogListResizableHeader
                columnKey="upstream"
                startResize={startResize}
                resetColumn={resetColumn}
              >
                上游
              </LogListResizableHeader>
              <LogListResizableHeader
                columnKey="credential"
                startResize={startResize}
                resetColumn={resetColumn}
              >
                凭据
              </LogListResizableHeader>
              <LogListResizableHeader
                columnKey="capability"
                startResize={startResize}
                resetColumn={resetColumn}
              >
                能力
              </LogListResizableHeader>
              <LogListResizableHeader
                columnKey="status"
                startResize={startResize}
                resetColumn={resetColumn}
              >
                状态
              </LogListResizableHeader>
              <LogListResizableHeader
                columnKey="tokens"
                className="text-right"
                startResize={startResize}
                resetColumn={resetColumn}
              >
                Tokens
              </LogListResizableHeader>
              <LogListResizableHeader
                columnKey="cost"
                className="text-right"
                startResize={startResize}
                resetColumn={resetColumn}
              >
                成本
              </LogListResizableHeader>
              <LogListResizableHeader
                columnKey="latency"
                className="text-right"
                startResize={startResize}
                resetColumn={resetColumn}
              >
                延迟
              </LogListResizableHeader>
              <LogListResizableHeader
                columnKey="ttfb"
                className="text-right"
                startResize={startResize}
                resetColumn={resetColumn}
              >
                首字节
              </LogListResizableHeader>
              <LogListResizableHeader
                columnKey="requestId"
                startResize={startResize}
                resetColumn={resetColumn}
              >
                请求 ID
              </LogListResizableHeader>
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
                  {virtualItems.map((row) => {
                    const item = items[row.index]
                    return (
                      <LogRow
                        key={row.key}
                        row={row}
                        item={item}
                        modelCatalogIndex={modelCatalogIndex}
                        gridTemplateColumns={logGridTemplateColumns}
                        showCallerColumn={showCallerColumn}
                        selected={item.id === selectedId}
                        onSelect={handleRowSelect}
                      />
                    )
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-2 border-t px-3 py-2">
          <PaginationControls
            page={data?.page ?? page}
            page_size={pageSize}
            total={data?.total ?? items.length}
            total_exact={listTotalExact}
            has_next={data?.has_next ?? false}
            has_prev={data?.has_prev ?? false}
            onPageChange={(next) => {
              setPage(next)
              parentRef.current?.scrollTo({ top: 0 })
            }}
            className="text-xs"
          />
          <div className="flex items-center gap-2">
            {isFetching && !isLoading ? (
              <span className="text-xs text-muted-foreground">正在同步...</span>
            ) : null}
            <Select
              value={String(pageSize)}
              onValueChange={(next) => {
                const size = Number(next)
                if (PAGE_SIZE_OPTIONS.includes(size as (typeof PAGE_SIZE_OPTIONS)[number])) {
                  setPageSize(size)
                  setPage(1)
                  parentRef.current?.scrollTo({ top: 0 })
                }
              }}
            >
              <SelectTrigger className="h-8 w-[72px] text-xs" aria-label="每页条数">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {PAGE_SIZE_OPTIONS.map((size) => (
                  <SelectItem key={size} value={String(size)}>
                    {size} 条/页
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
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
                {activeLogIdentity ? logModelIdentityTitle(activeLogIdentity) : '请求详情'}
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
                    {activeLogIdentity ? (
                      <LogModelIdentityFields identity={activeLogIdentity} />
                    ) : null}
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
                    <DetailField label="调用来源">
                      {activeLog.client_type === GATEWAY_CLIENT_TYPES.MODEL_CONNECTIVITY_PROBE
                        ? '模型探活'
                        : (activeLog.client_type ?? '—')}
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

const LogRow = memo(function LogRow({
  row,
  item,
  modelCatalogIndex,
  gridTemplateColumns,
  showCallerColumn,
  selected,
  onSelect,
}: Readonly<{
  row: VirtualItem
  item: GatewayLogItem
  modelCatalogIndex: LogModelCatalogIndex
  gridTemplateColumns: string
  showCallerColumn: boolean
  selected: boolean
  onSelect: (id: string) => void
}>): React.JSX.Element {
  const identity = resolveLogModelIdentity(item, modelCatalogIndex)

  return (
    <button
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: '100%',
        height: `${row.size.toString()}px`,
        transform: `translateY(${row.start.toString()}px)`,
        display: 'grid',
        gridTemplateColumns,
      }}
      className={cn(
        'cv-auto-row items-center border-b px-3 text-left text-xs transition-colors hover:bg-muted/40',
        selected ? 'bg-primary/5 ring-1 ring-inset ring-primary/20' : ''
      )}
      type="button"
      onClick={() => {
        onSelect(item.id)
      }}
    >
      <div className="truncate text-muted-foreground">{formatDateTime(item.created_at)}</div>
      {showCallerColumn ? (
        <div className="truncate" title={logCallerDisplayTitle(item)}>
          {logCallerDisplayText(item)}
        </div>
      ) : null}
      <div className="min-w-0 truncate font-mono" title={identity.invokeName ?? undefined}>
        {identity.invokeName ?? '—'}
      </div>
      <div
        className="truncate font-mono text-muted-foreground"
        title={identity.upstreamName ?? undefined}
      >
        {identity.upstreamName ?? '—'}
      </div>
      <div className="truncate" title={credentialDisplayTitle(item)}>
        {credentialDisplayText(item)}
      </div>
      <div>
        <CapabilityBadge capability={item.capability} />
      </div>
      <div className="flex items-center gap-1">
        <StatusBadge status={item.status} />
        {item.client_type === GATEWAY_CLIENT_TYPES.MODEL_CONNECTIVITY_PROBE ? (
          <Badge variant="outline" className="h-5 px-1 text-[10px]">
            探活
          </Badge>
        ) : null}
      </div>
      <div className="text-right tabular-nums">
        {(item.input_tokens + item.output_tokens).toLocaleString()}
      </div>
      <div className="text-right tabular-nums">{formatLogMoney(item)}</div>
      <div className="text-right tabular-nums">{formatMs(item.latency_ms)}</div>
      <div className="text-right tabular-nums text-muted-foreground">{formatMs(item.ttfb_ms)}</div>
      <div className="truncate font-mono text-muted-foreground">{item.request_id ?? item.id}</div>
    </button>
  )
})

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
    <div className="grid grid-cols-2 gap-2 md:grid-cols-5">
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
        icon={<Clock className="h-4 w-4" />}
        label="首字节"
        value={formatMs(log.ttfb_ms)}
        caption={
          typeof log.ttfb_ms === 'number' && log.latency_ms > 0
            ? `占 ${String(Math.round((log.ttfb_ms / log.latency_ms) * 100))}%`
            : undefined
        }
      />
      <MetricTile
        icon={<Server className="h-4 w-4" />}
        label="缓存"
        value={log.cache_hit ? '命中' : '未命中'}
        caption={
          log.cached_tokens > 0 || log.cache_creation_tokens > 0
            ? [
                log.cached_tokens > 0 && `${log.cached_tokens.toLocaleString()} 读`,
                log.cache_creation_tokens > 0 && `${log.cache_creation_tokens.toLocaleString()} 写`,
              ]
                .filter(Boolean)
                .join(' / ')
            : undefined
        }
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

function LogModelIdentityFields({
  identity,
}: Readonly<{ identity: LogModelIdentity }>): React.JSX.Element {
  return (
    <>
      <DetailField label="调用名" mono>
        {identity.invokeName ?? '—'}
      </DetailField>
      {identity.displayName ? (
        <DetailField label="显示名">{identity.displayName}</DetailField>
      ) : null}
      <DetailField label="上游" mono>
        {identity.upstreamName ?? '—'}
      </DetailField>
      {identity.registrationName && identity.registrationName !== identity.invokeName ? (
        <DetailField label="注册别名" mono>
          {identity.registrationName}
        </DetailField>
      ) : null}
      <DetailField label="模型 ID" mono>
        {identity.gatewayModelId ?? '—'}
      </DetailField>
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
