import { memo, type ReactNode } from 'react'

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
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { ConnectivityHealthStrip } from '@/features/gateway-models/connectivity-health-strip'
import { FILTER_ALL, USAGE_PERIOD_DAYS } from '@/features/gateway-models/constants'
import {
  GatewayModelCredentialFilterSelect,
  type GatewayModelCredentialFilterOption,
} from '@/features/gateway-models/gateway-model-credential-filter-select'
import { RegistryAbilityFilterSelect } from '@/features/gateway-models/registry-ability-filter-select'
import { channelLabel } from '@/features/gateway-models/utils'
import { GatewayRefreshButton } from '@/features/gateway-shared/gateway-refresh-button'
import { Info, MoreHorizontal, Plus, Search } from '@/lib/lucide-icons'
import { PROVIDER_CHANNEL_FILTER_HINT_GATEWAY } from '@/lib/provider-channel-hint'
import { cn } from '@/lib/utils'

import type { GatewayModelListToolbarProps } from './types'

export const GatewayModelListToolbar = memo(function GatewayModelListToolbar({
  capabilities,
  search,
  onSearchChange,
  providerFilter,
  onProviderFilterChange,
  abilityFilter,
  onAbilityFilterChange,
  credentialFilter = '',
  onCredentialFilterChange,
  credentialFilterOptions = [],
  credentialFilterLoading = false,
  selectedCredentialName,
  providerChoices,
  healthFilter,
  onHealthFilterChange,
  connectivitySummary,
  allModels,
  usageDays,
  onUsageDaysChange,
  canWrite,
  onTestAll,
  onTestUntested,
  onResyncAll,
  untestedTestableCount,
  testingAll,
  onDeleteFailed,
  deletingFailed,
  resyncingAll = false,
  batchBusy = false,
  onRefresh,
  isRefreshing = false,
  onRegister,
  onPreloadRegister,
  channelHint,
  deleteAllFilteredSlot,
}: GatewayModelListToolbarProps): React.JSX.Element {
  const showSearch = capabilities.search !== false
  const showCredentialFilter =
    capabilities.credentialFilter !== false && onCredentialFilterChange !== undefined
  const showChannelFilter = capabilities.channelFilter !== false
  const showAbilityFilter = capabilities.abilityFilter !== false
  const showHealthFilter = capabilities.healthFilter !== false
  const showUsageSummary = capabilities.usageSummary !== false
  const showChannelHint = capabilities.channelHint !== false
  const showDeleteAllMenu =
    capabilities.deleteAllFiltered !== false && deleteAllFilteredSlot !== undefined

  const credentialOptions = credentialFilterOptions as readonly GatewayModelCredentialFilterOption[]

  const hintContent: ReactNode = channelHint ?? PROVIDER_CHANNEL_FILTER_HINT_GATEWAY

  return (
    <div className="space-y-3 border-b p-3">
      <div className="flex flex-wrap items-center gap-2">
        {showSearch ? (
          <div className="relative min-w-0 flex-1 basis-[min(100%,220px)]">
            <Search className="pointer-events-none absolute left-2.5 top-2 h-4 w-4 text-muted-foreground" />
            <Input
              value={search}
              onChange={(e) => {
                onSearchChange(e.target.value)
              }}
              placeholder="搜索别名、底模、通道、凭据…"
              className="h-8 w-full pl-8 text-sm"
              aria-label="搜索模型"
            />
          </div>
        ) : null}

        {showCredentialFilter ? (
          <GatewayModelCredentialFilterSelect
            value={credentialFilter}
            onChange={onCredentialFilterChange}
            options={credentialOptions}
            loading={credentialFilterLoading}
            selectedCredentialName={selectedCredentialName}
          />
        ) : null}

        {showChannelFilter ? (
          <Select
            value={providerFilter || FILTER_ALL}
            onValueChange={(v) => {
              onProviderFilterChange(v === FILTER_ALL ? '' : v)
            }}
          >
            <SelectTrigger className="h-8 w-[130px] shrink-0 text-xs" aria-label="按接入通道筛选">
              <SelectValue placeholder="通道" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={FILTER_ALL}>全部通道</SelectItem>
              {providerChoices.map((id) => (
                <SelectItem key={id} value={id}>
                  {channelLabel(id)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        ) : null}

        {showAbilityFilter ? (
          <RegistryAbilityFilterSelect
            value={abilityFilter}
            onValueChange={onAbilityFilterChange}
          />
        ) : null}

        {showChannelHint ? (
          <TooltipProvider delayDuration={300}>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 shrink-0 text-muted-foreground"
                  aria-label="通道筛选说明"
                >
                  <Info className="h-4 w-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="bottom" className="max-w-xs text-xs">
                {hintContent}
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        ) : null}

        {onRefresh ? (
          <GatewayRefreshButton
            isFetching={isRefreshing}
            ariaLabel="刷新模型列表"
            className="h-8 w-8 shrink-0"
            onRefresh={onRefresh}
          />
        ) : null}

        {showDeleteAllMenu ? (
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

        {canWrite && onRegister ? (
          <Button
            size="sm"
            className="h-8 shrink-0"
            onMouseEnter={onPreloadRegister}
            onFocus={onPreloadRegister}
            onClick={onRegister}
          >
            <Plus className="mr-1.5 h-4 w-4" />
            添加模型
          </Button>
        ) : null}
      </div>

      {showHealthFilter || showUsageSummary ? (
        <div className="flex flex-wrap items-center gap-2">
          {showHealthFilter ? (
            <ConnectivityHealthStrip
              models={allModels}
              connectivitySummary={connectivitySummary}
              healthFilter={healthFilter}
              onHealthFilterChange={onHealthFilterChange}
              canWrite={canWrite}
              onTestAll={onTestAll}
              onTestUntested={onTestUntested}
              onResyncAll={onResyncAll}
              resyncingAll={resyncingAll}
              batchBusy={batchBusy}
              untestedTestableCount={untestedTestableCount}
              testingAll={testingAll}
              onDeleteFailed={onDeleteFailed}
              deletingFailed={deletingFailed}
            />
          ) : null}

          {showUsageSummary ? (
            <div className="ml-auto flex shrink-0 items-center gap-1.5">
              <div className="flex rounded-md bg-muted/50 p-0.5">
                {USAGE_PERIOD_DAYS.map((d) => (
                  <button
                    key={d}
                    type="button"
                    className={cn(
                      'rounded px-2 py-1 text-xs font-medium transition-colors',
                      usageDays === d
                        ? 'bg-background text-foreground shadow-sm'
                        : 'text-muted-foreground hover:text-foreground'
                    )}
                    onClick={() => {
                      onUsageDaysChange(d)
                    }}
                  >
                    {d === 1 ? '24h' : d === 7 ? '7d' : '30d'}
                  </button>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  )
})
