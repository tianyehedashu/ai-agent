import { useState } from 'react'
import type React from 'react'

import type { MyPriceRow } from '@/api/gateway'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { PricingBadge } from '@/features/gateway-pricing/pricing-badge'
import {
  Check,
  CheckCircle2,
  ChevronsUpDown,
  CircleDashed,
  Loader2,
  XCircle,
} from '@/lib/lucide-icons'
import { cn } from '@/lib/utils'
import type { DisplayCurrency } from '@/types/money'
import type { ModelTestStatus } from '@/types/user-model'

import {
  PLAYGROUND_MODE_LABELS,
  type ModelCandidate,
  type PlaygroundMode,
} from './playground-mode-filter'

import type { PlaygroundTeamModelGroup } from './playground-proxy-team'

export const CUSTOM_MODEL_SENTINEL = '__custom__'

export interface RouteCandidate {
  name: string
  primaryModels: string[]
}

export interface PlaygroundModelFieldProps {
  modelSelectId: string
  modelCustomId: string
  model: string
  customModel: boolean
  onModelChange: (value: string) => void
  onCustomModelChange: (custom: boolean, model?: string) => void
  routeCandidates: RouteCandidate[]
  teamCandidates: ModelCandidate[]
  /** multi-grant vkey：按工作区分组的团队模型（优先于扁平 teamCandidates） */
  teamModelGroups?: readonly PlaygroundTeamModelGroup[]
  personalCandidates: ModelCandidate[]
  filteredModels: ModelCandidate[]
  selectedCandidate: ModelCandidate | undefined
  selectedRoute: RouteCandidate | undefined
  priceByName: Map<string, MyPriceRow>
  currency: DisplayCurrency
  playgroundMode: PlaygroundMode
  modelsLoading: boolean
  onOpenChange?: (open: boolean) => void
  /** 个人模型分组标题 */
  personalModelsLabel?: string
  /** 自定义模型输入框 placeholder */
  customModelPlaceholder?: string
}

function modelCommandItemValue(item: ModelCandidate): string {
  return [item.name, item.provider, item.capability, item.teamSlug].filter(Boolean).join(' ')
}

function routeCommandItemValue(item: RouteCandidate): string {
  return [item.name, ...item.primaryModels, '路由'].join(' ')
}

export function PlaygroundModelField({
  modelSelectId,
  modelCustomId,
  model,
  customModel,
  onModelChange,
  onCustomModelChange,
  routeCandidates,
  teamCandidates,
  teamModelGroups,
  personalCandidates,
  filteredModels,
  selectedCandidate,
  selectedRoute,
  priceByName,
  currency,
  playgroundMode,
  modelsLoading,
  onOpenChange,
  personalModelsLabel = '个人模型',
  customModelPlaceholder = '输入模型别名或虚拟路由名（也可输入未列出的名称）',
}: Readonly<PlaygroundModelFieldProps>): React.JSX.Element {
  const [open, setOpen] = useState(false)

  const listEmpty = filteredModels.length === 0 && routeCandidates.length === 0
  const triggerPlaceholder = listEmpty
    ? `暂无支持「${PLAYGROUND_MODE_LABELS[playgroundMode]}」的模型或路由`
    : '选择模型或虚拟路由'
  const triggerLabel = modelsLoading ? '加载模型…' : model || triggerPlaceholder

  const handleOpenChange = (next: boolean): void => {
    setOpen(next)
    onOpenChange?.(next)
  }

  const handlePick = (value: string): void => {
    onCustomModelChange(false, value)
    setOpen(false)
  }

  const handleManualInput = (): void => {
    onCustomModelChange(true, '')
    setOpen(false)
  }

  return (
    <div className="space-y-1.5">
      <Label htmlFor={customModel ? modelCustomId : modelSelectId}>
        模型 <span className="text-destructive">*</span>
      </Label>
      {customModel ? (
        <div className="flex gap-2">
          <Input
            id={modelCustomId}
            value={model}
            onChange={(e) => {
              onModelChange(e.target.value)
            }}
            placeholder={customModelPlaceholder}
            autoComplete="off"
            spellCheck={false}
            className="font-mono"
            translate="no"
          />
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => {
              onCustomModelChange(false, routeCandidates[0]?.name || filteredModels[0]?.name || '')
            }}
            disabled={listEmpty}
          >
            从列表选
          </Button>
        </div>
      ) : (
        <Popover open={open} onOpenChange={handleOpenChange}>
          <PopoverTrigger asChild>
            <Button
              id={modelSelectId}
              type="button"
              variant="outline"
              role="combobox"
              aria-expanded={open}
              disabled={modelsLoading && listEmpty}
              className={cn(
                'w-full justify-between font-normal',
                model ? 'font-mono' : 'text-muted-foreground'
              )}
            >
              <span className="flex min-w-0 items-center gap-2 truncate">
                {modelsLoading ? (
                  <Loader2
                    className="h-4 w-4 shrink-0 animate-spin opacity-60"
                    aria-hidden="true"
                  />
                ) : null}
                <span className="truncate" translate={model ? 'no' : undefined}>
                  {triggerLabel}
                </span>
              </span>
              <ChevronsUpDown className="h-4 w-4 shrink-0 opacity-50" aria-hidden="true" />
            </Button>
          </PopoverTrigger>
          <PopoverContent
            className="w-[max(var(--radix-popover-trigger-width),20rem)] max-w-[min(24rem,calc(100vw-2rem))] p-0"
            align="start"
            collisionPadding={8}
          >
            <Command>
              <CommandInput placeholder="搜索模型别名、路由…" />
              <CommandList>
                <CommandEmpty>未找到匹配的模型或路由</CommandEmpty>
                {routeCandidates.length > 0 ? (
                  <CommandGroup heading="虚拟路由">
                    {routeCandidates.map((item) => (
                      <CommandItem
                        key={`route-${item.name}`}
                        value={routeCommandItemValue(item)}
                        onSelect={() => {
                          handlePick(item.name)
                        }}
                      >
                        <Check
                          className={cn(
                            'mr-2 h-4 w-4 shrink-0',
                            model === item.name ? 'opacity-100' : 'opacity-0'
                          )}
                          aria-hidden="true"
                        />
                        <span className="flex min-w-0 flex-1 items-center justify-between gap-3">
                          <span className="min-w-0 flex-1 truncate font-mono" translate="no">
                            {item.name}
                          </span>
                          <Badge variant="outline" className="shrink-0 text-muted-foreground">
                            路由
                          </Badge>
                        </span>
                      </CommandItem>
                    ))}
                  </CommandGroup>
                ) : null}
                {teamModelGroups && teamModelGroups.length > 0
                  ? teamModelGroups.map((group) => (
                      <CommandGroup key={group.groupKey} heading={group.label}>
                        {group.models.map((item) => (
                          <ModelCommandItem
                            key={`team-${group.groupKey}-${item.name}`}
                            item={item}
                            selected={model === item.name}
                            priceRow={priceByName.get(item.name)}
                            currency={currency}
                            onPick={handlePick}
                          />
                        ))}
                      </CommandGroup>
                    ))
                  : null}
                {!teamModelGroups?.length && teamCandidates.length > 0 ? (
                  <CommandGroup heading="团队模型">
                    {teamCandidates.map((item) => (
                      <ModelCommandItem
                        key={`team-${item.name}`}
                        item={item}
                        selected={model === item.name}
                        priceRow={priceByName.get(item.name)}
                        currency={currency}
                        onPick={handlePick}
                      />
                    ))}
                  </CommandGroup>
                ) : null}
                {!teamModelGroups?.length && personalCandidates.length > 0 ? (
                  <CommandGroup heading={personalModelsLabel}>
                    {personalCandidates.map((item) => (
                      <ModelCommandItem
                        key={`personal-${item.name}`}
                        item={item}
                        selected={model === item.name}
                        priceRow={priceByName.get(item.name)}
                        currency={currency}
                        onPick={handlePick}
                      />
                    ))}
                  </CommandGroup>
                ) : null}
                <CommandGroup heading="其他">
                  <CommandItem
                    value={`${CUSTOM_MODEL_SENTINEL} 手动输入`}
                    onSelect={handleManualInput}
                  >
                    <span className="text-muted-foreground">✏️ 手动输入…</span>
                  </CommandItem>
                </CommandGroup>
              </CommandList>
            </Command>
          </PopoverContent>
        </Popover>
      )}
      <ModelHint
        loading={modelsLoading}
        selected={selectedCandidate}
        selectedRoute={selectedRoute}
        empty={listEmpty}
        mode={playgroundMode}
      />
    </div>
  )
}

function ModelCommandItem({
  item,
  selected,
  priceRow,
  currency,
  onPick,
}: Readonly<{
  item: ModelCandidate
  selected: boolean
  priceRow?: MyPriceRow
  currency: DisplayCurrency
  onPick: (name: string) => void
}>): React.JSX.Element {
  return (
    <CommandItem
      value={modelCommandItemValue(item)}
      className="[contain-intrinsic-size:0_44px] [content-visibility:auto]"
      onSelect={() => {
        onPick(item.name)
      }}
    >
      <Check
        className={cn('mr-2 h-4 w-4 shrink-0', selected ? 'opacity-100' : 'opacity-0')}
        aria-hidden="true"
      />
      <span className="flex min-w-0 flex-1 items-center justify-between gap-3">
        <span className="min-w-0 flex-1 truncate font-mono" translate="no">
          {item.name}
        </span>
        <span className="flex shrink-0 items-center gap-2">
          <PricingBadge row={priceRow} currency={currency} className="hidden sm:inline" />
          <ModelStatusBadge status={item.status} />
        </span>
      </span>
    </CommandItem>
  )
}

function ModelStatusBadge({ status }: Readonly<{ status: ModelTestStatus }>): React.JSX.Element {
  if (status === 'success') {
    return (
      <Badge variant="outline" className="gap-1 border-emerald-500/40 text-emerald-600">
        <CheckCircle2 className="h-3 w-3" aria-hidden="true" />
        已通过
      </Badge>
    )
  }
  if (status === 'failed') {
    return (
      <Badge variant="outline" className="gap-1 border-destructive/40 text-destructive">
        <XCircle className="h-3 w-3" aria-hidden="true" />
        失败
      </Badge>
    )
  }
  return (
    <Badge variant="outline" className="gap-1 text-muted-foreground">
      <CircleDashed className="h-3 w-3" aria-hidden="true" />
      未测试
    </Badge>
  )
}

function ModelHint({
  loading,
  selected,
  selectedRoute,
  empty,
  mode,
}: Readonly<{
  loading: boolean
  selected: ModelCandidate | undefined
  selectedRoute: RouteCandidate | undefined
  empty: boolean
  mode: PlaygroundMode
}>): React.JSX.Element | null {
  if (loading) {
    return <p className="text-xs text-muted-foreground">加载中…</p>
  }
  if (selectedRoute) {
    return (
      <p className="text-xs text-muted-foreground">
        虚拟路由 · 主模型：{selectedRoute.primaryModels.join('、') || '—'}
      </p>
    )
  }
  if (empty) {
    return (
      <p className="text-xs text-muted-foreground">
        暂无支持「{PLAYGROUND_MODE_LABELS[mode]}」的模型。
      </p>
    )
  }
  if (selected?.status === 'failed') {
    return <p className="text-xs text-destructive">连通性测试失败。</p>
  }
  return null
}
