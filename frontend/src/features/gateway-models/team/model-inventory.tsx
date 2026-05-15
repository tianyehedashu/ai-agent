import { Loader2, Search } from 'lucide-react'

import type { GatewayModel, GatewayModelRouteUsageItem } from '@/api/gateway'
import { ModelStatusBadge } from '@/components/model-status-badge'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { PROVIDER_CHANNEL_FILTER_HINT_GATEWAY } from '@/lib/provider-channel-hint'
import { cn } from '@/lib/utils'

import { FILTER_ALL } from '../constants'
import { channelLabel, classifyFailureReason, formatUsageLine } from '../utils'
import { ModelCapabilityBadges } from './model-capability-badges'

interface ModelInventoryProps {
  models: GatewayModel[]
  selectedId: string | null
  onSelect: (id: string) => void
  isLoading: boolean
  search: string
  onSearchChange: (v: string) => void
  providerFilter: string
  onProviderFilterChange: (v: string) => void
  providerChoices: string[]
  usageDays: 1 | 7 | 30
  usageByRouteName: Map<string, GatewayModelRouteUsageItem>
  usageLoading: boolean
  highlightModelId?: string
}

export function ModelInventory({
  models,
  selectedId,
  onSelect,
  isLoading,
  search,
  onSearchChange,
  providerFilter,
  onProviderFilterChange,
  providerChoices,
  usageDays,
  usageByRouteName,
  usageLoading,
  highlightModelId,
}: ModelInventoryProps): React.JSX.Element {
  return (
    <div className="flex min-h-0 flex-col rounded-lg border bg-card">
      <div className="space-y-2 border-b p-3">
        <div className="relative">
          <Search className="pointer-events-none absolute left-2.5 top-2 h-4 w-4 text-muted-foreground" />
          <Input
            value={search}
            onChange={(e) => {
              onSearchChange(e.target.value)
            }}
            placeholder="搜索注册别名…"
            className="h-8 pl-8 text-sm"
            aria-label="搜索注册别名"
          />
        </div>
        <Select
          value={providerFilter || FILTER_ALL}
          onValueChange={(v) => {
            onProviderFilterChange(v === FILTER_ALL ? '' : v)
          }}
        >
          <SelectTrigger className="h-8 text-xs" aria-label="按接入通道筛选">
            <SelectValue placeholder="全部通道" />
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
        <p className="text-xs text-muted-foreground">{PROVIDER_CHANNEL_FILTER_HINT_GATEWAY}</p>
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
            {models.map((m) => {
              const selected = m.id === selectedId
              const highlighted = m.id === highlightModelId
              const urow = usageByRouteName.get(m.name)
              const wsReq = urow?.workspace.requests ?? 0
              const wsTok =
                (urow?.workspace.input_tokens ?? 0) + (urow?.workspace.output_tokens ?? 0)
              const usageText =
                !usageLoading && urow
                  ? formatUsageLine(usageDays, wsReq, wsTok, urow.workspace.cost_usd)
                  : null
              const failShort =
                m.last_test_status === 'failed' ? classifyFailureReason(m.last_test_reason) : null

              return (
                <li key={m.id}>
                  <button
                    type="button"
                    onClick={() => {
                      onSelect(m.id)
                    }}
                    className={cn(
                      'w-full px-3 py-2.5 text-left transition-colors hover:bg-muted/40',
                      selected && 'bg-primary/10',
                      highlighted && !selected && 'bg-primary/5'
                    )}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0 flex-1">
                        <p className="truncate font-mono text-sm font-medium">{m.name}</p>
                        <p className="mt-0.5 text-xs text-muted-foreground">
                          {channelLabel(m.provider)} · {m.real_model}
                        </p>
                      </div>
                      <ModelStatusBadge
                        status={m.last_test_status}
                        testedAt={m.last_tested_at}
                        reason={m.last_test_reason}
                        className="shrink-0"
                      />
                    </div>
                    {failShort ? (
                      <p className="mt-1 text-xs text-destructive">{failShort}</p>
                    ) : null}
                    {usageLoading ? (
                      <p className="mt-1 text-xs text-muted-foreground">用量…</p>
                    ) : usageText ? (
                      <p className="mt-1 text-xs tabular-nums text-muted-foreground">{usageText}</p>
                    ) : null}
                    <div className="mt-1.5">
                      <ModelCapabilityBadges model={m} compact />
                    </div>
                    {!m.enabled ? (
                      <p className="mt-1 text-xs text-amber-600 dark:text-amber-400">已禁用</p>
                    ) : null}
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </ScrollArea>
    </div>
  )
}
