/**
 * 统一模型工具栏：归属筛选 + 搜索 + 通道/健康筛选。
 */

import type React from 'react'
import { memo } from 'react'

import type { GatewayTeam } from '@/api/gateway/teams'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { ConnectivityHealthStrip } from '@/features/gateway-models/connectivity-health-strip'
import { FILTER_ALL, type HealthFilter } from '@/features/gateway-models/constants'
import {
  shouldShowUnifiedTeamFilter,
  type UnifiedModelScopeFilter,
} from '@/features/gateway-models/unified/unified-models-filters'
import type { ModelWithConnectivityStatus } from '@/features/gateway-models/utils'
import { channelLabel } from '@/features/gateway-models/utils'
import { GatewayRefreshButton } from '@/features/gateway-shared/gateway-refresh-button'
import { GatewayTeamCombobox } from '@/features/gateway-teams/gateway-team-combobox'
import { GATEWAY_FILTER_ALL } from '@/features/gateway-usage/gateway-filter-combobox'
import { MoreHorizontal, Plus, Search } from '@/lib/lucide-icons'

const SCOPE_FILTER_OPTIONS: ReadonlyArray<{
  value: UnifiedModelScopeFilter
  label: string
  countKey: 'total' | 'personal' | 'team' | 'system'
}> = [
  { value: 'all', label: '全部', countKey: 'total' },
  { value: 'personal', label: '个人', countKey: 'personal' },
  { value: 'team', label: '团队', countKey: 'team' },
  { value: 'system', label: '系统', countKey: 'system' },
]

export interface UnifiedModelsToolbarProps {
  search: string
  onSearchChange: (value: string) => void
  scopeFilter: UnifiedModelScopeFilter
  onScopeFilterChange: (value: UnifiedModelScopeFilter) => void
  providerFilter: string
  onProviderFilterChange: (value: string) => void
  providerChoices: readonly string[]
  teamFilter?: string
  onTeamFilterChange?: (teamId: string) => void
  teamsWithModels?: readonly GatewayTeam[]
  healthFilter: HealthFilter
  onHealthFilterChange: (value: HealthFilter) => void
  connectivitySummary: {
    total: number
    success: number
    failed: number
    unknown: number
  }
  counts: {
    personal: number
    team: number
    system: number
    total: number
  }
  filteredTotal: number
  hasActiveFilters: boolean
  isRefreshing?: boolean
  onRefresh?: () => void
  showAdd?: boolean
  onAdd?: () => void
  /** 探活统计与批量运维 */
  showBatchOps?: boolean
  connectivityModels?: readonly ModelWithConnectivityStatus[]
  canWrite?: boolean
  onTestAll?: () => void
  onTestUntested?: () => void
  untestedTestableCount?: number
  testingAll?: boolean
  batchBusy?: boolean
  onResyncAll?: () => void
  resyncingAll?: boolean
  onDeleteFailed?: () => void
  deletingFailed?: boolean
  deleteAllFilteredSlot?: React.ReactNode
}

export const UnifiedModelsToolbar = memo(function UnifiedModelsToolbar({
  search,
  onSearchChange,
  scopeFilter,
  onScopeFilterChange,
  providerFilter,
  onProviderFilterChange,
  providerChoices,
  teamFilter,
  onTeamFilterChange,
  teamsWithModels = [],
  healthFilter,
  onHealthFilterChange,
  connectivitySummary,
  counts,
  filteredTotal,
  hasActiveFilters,
  isRefreshing = false,
  onRefresh,
  showAdd = false,
  onAdd,
  showBatchOps = false,
  connectivityModels = [],
  canWrite = false,
  onTestAll,
  onTestUntested,
  untestedTestableCount = 0,
  testingAll = false,
  batchBusy = false,
  onResyncAll,
  resyncingAll = false,
  onDeleteFailed,
  deletingFailed = false,
  deleteAllFilteredSlot,
}: UnifiedModelsToolbarProps): React.JSX.Element {
  const countByKey = {
    total: counts.total,
    personal: counts.personal,
    team: counts.team,
    system: counts.system,
  }

  const showTeamFilter =
    shouldShowUnifiedTeamFilter(scopeFilter, teamsWithModels.length) &&
    onTeamFilterChange !== undefined

  return (
    <div className="space-y-2 border-b p-3">
      <div className="flex flex-wrap items-center gap-2">
        {SCOPE_FILTER_OPTIONS.map((option) => {
          const count = countByKey[option.countKey]
          const active = scopeFilter === option.value
          return (
            <Button
              key={option.value}
              type="button"
              size="sm"
              variant={active ? 'secondary' : 'outline'}
              className="h-7 text-xs"
              onClick={() => {
                onScopeFilterChange(option.value)
              }}
            >
              {option.label}
              <Badge variant={active ? 'outline' : 'secondary'} className="ml-1.5 font-normal">
                {count}
              </Badge>
            </Button>
          )
        })}
        {hasActiveFilters ? (
          <span className="text-xs text-muted-foreground">筛选结果 {filteredTotal} 条</span>
        ) : null}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Select
          value={providerFilter || FILTER_ALL}
          onValueChange={(v) => {
            onProviderFilterChange(v === FILTER_ALL ? '' : v)
          }}
        >
          <SelectTrigger className="h-8 w-[140px] text-xs">
            <SelectValue placeholder="通道" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={FILTER_ALL}>全部通道</SelectItem>
            {providerChoices.map((p) => (
              <SelectItem key={p} value={p}>
                {channelLabel(p)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {showTeamFilter ? (
          <GatewayTeamCombobox
            allowAll
            allLabel="全部团队"
            allSelectedShowsPlaceholder
            value={
              teamFilter && teamFilter !== GATEWAY_FILTER_ALL ? teamFilter : GATEWAY_FILTER_ALL
            }
            onChange={onTeamFilterChange}
            teams={teamsWithModels}
            placeholder="按团队筛选"
            className="h-8 max-w-[11rem] text-xs"
            active={teamFilter !== '' && teamFilter !== GATEWAY_FILTER_ALL}
          />
        ) : null}

        <div className="ml-auto flex flex-wrap items-center gap-2">
          <div className="relative min-w-[200px] max-w-xs flex-1 sm:flex-none">
            <Search className="pointer-events-none absolute left-2.5 top-2 h-4 w-4 text-muted-foreground" />
            <Input
              value={search}
              onChange={(e) => {
                onSearchChange(e.target.value)
              }}
              placeholder="名称、通道、归属、上游 ID"
              className="h-8 pl-8 text-sm"
              aria-label="筛选模型"
            />
          </div>
          {onRefresh ? (
            <GatewayRefreshButton
              isFetching={isRefreshing}
              ariaLabel="刷新模型"
              onRefresh={onRefresh}
            />
          ) : null}
          {deleteAllFilteredSlot ? (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  type="button"
                  variant="outline"
                  size="icon"
                  className="h-8 w-8 shrink-0"
                  aria-label="更多批量操作"
                >
                  <MoreHorizontal className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">{deleteAllFilteredSlot}</DropdownMenuContent>
            </DropdownMenu>
          ) : null}
          {showAdd && onAdd ? (
            <Button size="sm" onClick={onAdd}>
              <Plus className="mr-1.5 h-4 w-4" />
              添加模型
            </Button>
          ) : null}
        </div>
      </div>

      <ConnectivityHealthStrip
        models={connectivityModels}
        connectivitySummary={connectivitySummary}
        healthFilter={healthFilter}
        onHealthFilterChange={onHealthFilterChange}
        canWrite={showBatchOps && canWrite}
        onTestAll={showBatchOps ? onTestAll : undefined}
        onTestUntested={showBatchOps ? onTestUntested : undefined}
        untestedTestableCount={untestedTestableCount}
        testingAll={testingAll}
        batchBusy={batchBusy}
        onResyncAll={showBatchOps ? onResyncAll : undefined}
        resyncingAll={resyncingAll}
        onDeleteFailed={showBatchOps ? onDeleteFailed : undefined}
        deletingFailed={deletingFailed}
      />
    </div>
  )
})
