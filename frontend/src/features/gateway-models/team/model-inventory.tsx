import { memo } from 'react'

import type { GatewayModel, GatewayModelRouteUsageItem } from '@/api/gateway'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { Info, Loader2, Plus, Search } from '@/lib/lucide-icons'
import { PROVIDER_CHANNEL_FILTER_HINT_GATEWAY } from '@/lib/provider-channel-hint'
import { cn } from '@/lib/utils'

import { ConnectivityHealthStrip } from '../connectivity-health-strip'
import {
  FILTER_ALL,
  type HealthFilter,
  USAGE_PERIOD_DAYS,
  type UsagePeriodDays,
} from '../constants'
import { channelLabel } from '../utils'
import { ModelInventoryRow } from './model-inventory-row'

interface ModelInventoryProps {
  models: GatewayModel[]
  allModels: GatewayModel[]
  selectedId: string | null
  /** 无 ``getModelHref`` 时用于行点击选中（链接模式可省略） */
  onSelect?: (id: string) => void
  /** 有则行渲染为 Link（凭据筛选等深链场景） */
  getModelHref?: (modelId: string) => string
  isLoading: boolean
  search: string
  onSearchChange: (v: string) => void
  providerFilter: string
  onProviderFilterChange: (v: string) => void
  providerChoices: string[]
  usageDays: UsagePeriodDays
  onUsageDaysChange: (d: UsagePeriodDays) => void
  usageByRouteName: Map<string, GatewayModelRouteUsageItem>
  usageLoading: boolean
  highlightModelId?: string
  healthFilter: HealthFilter
  onHealthFilterChange: (f: HealthFilter) => void
  canWrite: boolean
  onTestAll?: () => void
  testingAll?: boolean
  onRegister?: () => void
  onPreloadRegister?: () => void
  /** 列表行链至详情时预加载详情 chunk */
  onPreloadRowNavigate?: () => void
}

export const ModelInventory = memo(function ModelInventory({
  models,
  allModels,
  selectedId,
  onSelect,
  getModelHref,
  isLoading,
  search,
  onSearchChange,
  providerFilter,
  onProviderFilterChange,
  providerChoices,
  usageDays,
  onUsageDaysChange,
  usageByRouteName,
  usageLoading,
  highlightModelId,
  healthFilter,
  onHealthFilterChange,
  canWrite,
  onTestAll,
  testingAll,
  onRegister,
  onPreloadRegister,
  onPreloadRowNavigate,
}: ModelInventoryProps): React.JSX.Element {
  const showToolbar = allModels.length > 0

  return (
    <div className="flex min-h-0 flex-col rounded-lg border bg-card">
      <div className="space-y-2.5 border-b p-3">
        <div className="flex gap-2">
          <div className="relative min-w-0 flex-1">
            <Search className="pointer-events-none absolute left-2.5 top-2 h-4 w-4 text-muted-foreground" />
            <Input
              value={search}
              onChange={(e) => {
                onSearchChange(e.target.value)
              }}
              placeholder="搜索别名、底模、通道…"
              className="h-8 pl-8 text-sm"
              aria-label="搜索模型"
            />
          </div>
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
                {PROVIDER_CHANNEL_FILTER_HINT_GATEWAY}
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>

        {showToolbar ? (
          <div className="flex flex-wrap items-center gap-2">
            <ConnectivityHealthStrip
              models={allModels}
              healthFilter={healthFilter}
              onHealthFilterChange={onHealthFilterChange}
              canWrite={canWrite}
              onTestAll={onTestAll}
              testingAll={testingAll}
            />
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
              {canWrite && onRegister ? (
                <Button
                  size="sm"
                  variant="outline"
                  className="h-7 text-xs sm:hidden"
                  onMouseEnter={onPreloadRegister}
                  onFocus={onPreloadRegister}
                  onClick={onRegister}
                >
                  <Plus className="mr-1 h-3 w-3" />
                  注册
                </Button>
              ) : null}
            </div>
          </div>
        ) : null}
      </div>
      <ScrollArea className="min-h-[280px] flex-1">
        {isLoading ? (
          <div className="flex items-center justify-center gap-2 py-12 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            加载中…
          </div>
        ) : models.length === 0 ? (
          <p className="px-3 py-12 text-center text-sm text-muted-foreground">无匹配模型</p>
        ) : (
          <ul className="divide-y">
            {models.map((m) => (
              <ModelInventoryRow
                key={m.id}
                model={m}
                selected={m.id === selectedId}
                highlighted={m.id === highlightModelId}
                usageDays={usageDays}
                usageRow={usageByRouteName.get(m.name)}
                usageLoading={usageLoading}
                href={getModelHref?.(m.id)}
                onSelect={getModelHref ? undefined : onSelect}
                onPreloadNavigate={getModelHref ? onPreloadRowNavigate : undefined}
              />
            ))}
          </ul>
        )}
      </ScrollArea>
    </div>
  )
})
