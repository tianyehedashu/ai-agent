import { memo, useCallback, useMemo } from 'react'

import { Link } from 'react-router-dom'

import type { GatewayModel, MyPriceRow } from '@/api/gateway'
import { ModelStatusBadge } from '@/components/model-status-badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import { TooltipProvider } from '@/components/ui/tooltip'
import {
  moveOrderedModelList,
  toggleModelSet,
  toggleOrderedModelList,
} from '@/features/gateway-models/utils'
import { GATEWAY_DISPLAY_CURRENCY } from '@/features/gateway-pricing/display-currency'
import { PricingBadge } from '@/features/gateway-pricing/pricing-badge'
import { ChevronDown, ChevronUp } from '@/lib/lucide-icons'
import { cn } from '@/lib/utils'
import type { DisplayCurrency } from '@/types/money'

const PICKER_ROW_CV = '[contain-intrinsic-size:auto_2.75rem] [content-visibility:auto]' as const

interface RouteModelPickerRowProps {
  model: GatewayModel
  checked: boolean
  /** 在 selected 中的顺序；未选中为 -1 */
  order: number
  disabled: boolean
  label: string
  onToggle: (modelName: string, checked: boolean) => void
  showOrderControls?: boolean
  selectedCount?: number
  onMove?: (order: number, dir: -1 | 1) => void
  priceRow?: MyPriceRow
  currency?: DisplayCurrency
}

export const RouteModelPickerRow = memo(function RouteModelPickerRow({
  model,
  checked,
  order,
  disabled,
  label,
  onToggle,
  showOrderControls = false,
  selectedCount = 0,
  onMove,
  priceRow,
  currency = GATEWAY_DISPLAY_CURRENCY,
}: RouteModelPickerRowProps): React.JSX.Element {
  return (
    <li
      className={cn(
        PICKER_ROW_CV,
        'flex items-center gap-2 rounded px-1 py-1 hover:bg-muted/30',
        checked && 'bg-primary/5'
      )}
    >
      <Checkbox
        checked={checked}
        disabled={disabled}
        onCheckedChange={(c) => {
          onToggle(model.name, c === true)
        }}
        aria-label={`${label} ${model.name}`}
      />
      <span className="min-w-0 flex-1 truncate font-mono text-sm">{model.name}</span>
      <PricingBadge row={priceRow} currency={currency} className="hidden lg:inline" />
      <ModelStatusBadge
        status={model.last_test_status}
        testedAt={model.last_tested_at}
        reason={model.last_test_reason}
        entitlementStatus={model.entitlement_status}
        entitlementResetAt={model.entitlement_reset_at}
        compact
        withProvider={false}
      />
      {checked && showOrderControls && !disabled && onMove ? (
        <div className="flex shrink-0 gap-0.5">
          <Button
            type="button"
            size="icon"
            variant="ghost"
            className="h-7 w-7"
            disabled={order <= 0}
            onClick={() => {
              onMove(order, -1)
            }}
            aria-label="上移"
          >
            <ChevronUp className="h-4 w-4" />
          </Button>
          <Button
            type="button"
            size="icon"
            variant="ghost"
            className="h-7 w-7"
            disabled={order < 0 || order >= selectedCount - 1}
            onClick={() => {
              onMove(order, 1)
            }}
            aria-label="下移"
          >
            <ChevronDown className="h-4 w-4" />
          </Button>
        </div>
      ) : null}
    </li>
  )
})

interface RouteOrderedModelPickerProps {
  models: readonly GatewayModel[]
  selected: string[]
  onSelectedChange: (next: string[]) => void
  disabled?: boolean
  label: string
  emptyHint?: string
  showOrderControls?: boolean
  priceByName?: Map<string, MyPriceRow>
  currency?: DisplayCurrency
}

export function RouteOrderedModelPicker({
  models,
  selected,
  onSelectedChange,
  disabled = false,
  label,
  emptyHint = '暂无已启用的注册模型',
  showOrderControls = true,
  priceByName,
  currency = GATEWAY_DISPLAY_CURRENCY,
}: RouteOrderedModelPickerProps): React.JSX.Element {
  const selectedSet = useMemo(() => new Set(selected), [selected])
  const orderByName = useMemo(
    () => new Map(selected.map((name, index) => [name, index])),
    [selected]
  )

  const handleToggle = useCallback(
    (name: string, checked: boolean): void => {
      onSelectedChange(toggleOrderedModelList(selected, name, checked))
    },
    [selected, onSelectedChange]
  )

  const handleMove = useCallback(
    (order: number, dir: -1 | 1): void => {
      onSelectedChange(moveOrderedModelList(selected, order, dir))
    },
    [selected, onSelectedChange]
  )

  return (
    <section className="space-y-2">
      <Label className="text-xs font-semibold uppercase text-muted-foreground">{label}</Label>
      {models.length === 0 ? (
        <div className="space-y-2 text-sm text-muted-foreground">
          <p>{emptyHint}</p>
          <p>
            请先在{' '}
            <Link
              to="/gateway/models?tab=shared"
              className="text-primary underline-offset-4 hover:underline"
            >
              模型管理
            </Link>{' '}
            注册并启用模型。
          </p>
        </div>
      ) : (
        <>
          <TooltipProvider delayDuration={200}>
            <ul className="space-y-1 rounded-md border p-2">
              {models.map((model) => {
                const checked = selectedSet.has(model.name)
                const order = orderByName.get(model.name) ?? -1
                return (
                  <RouteModelPickerRow
                    key={model.id}
                    model={model}
                    checked={checked}
                    order={order}
                    disabled={disabled}
                    label={label}
                    onToggle={handleToggle}
                    showOrderControls={showOrderControls}
                    selectedCount={selected.length}
                    onMove={showOrderControls && !disabled ? handleMove : undefined}
                    priceRow={priceByName?.get(model.name)}
                    currency={currency}
                  />
                )
              })}
            </ul>
          </TooltipProvider>
          {selected.length > 0 ? (
            <p className="text-xs text-muted-foreground">当前顺序：{selected.join(' → ')}</p>
          ) : null}
        </>
      )}
    </section>
  )
}

interface RouteFallbackModelPickerProps {
  models: readonly GatewayModel[]
  selected: string[]
  onSelectedChange: (next: string[]) => void
  disabled?: boolean
  label: string
  description?: string
  excludeNames?: readonly string[]
  priceByName?: Map<string, MyPriceRow>
  currency?: DisplayCurrency
}

export function RouteFallbackModelPicker({
  models,
  selected,
  onSelectedChange,
  disabled = false,
  label,
  description,
  excludeNames = [],
  priceByName,
  currency = GATEWAY_DISPLAY_CURRENCY,
}: RouteFallbackModelPickerProps): React.JSX.Element {
  const exclude = useMemo(() => new Set(excludeNames), [excludeNames])
  const candidates = useMemo(() => models.filter((m) => !exclude.has(m.name)), [models, exclude])
  const selectedSet = useMemo(() => new Set(selected), [selected])

  const handleToggle = useCallback(
    (name: string, checked: boolean): void => {
      onSelectedChange(toggleModelSet(selected, name, checked))
    },
    [selected, onSelectedChange]
  )

  return (
    <section className="space-y-2">
      <div>
        <Label className="text-xs">{label}</Label>
        {description ? <p className="mt-0.5 text-xs text-muted-foreground">{description}</p> : null}
      </div>
      {candidates.length === 0 ? (
        <p className="text-sm text-muted-foreground">暂无可选模型（请先配置主模型或注册模型）</p>
      ) : (
        <TooltipProvider delayDuration={200}>
          <ul className="max-h-40 space-y-1 overflow-y-auto rounded-md border p-2">
            {candidates.map((model) => (
              <RouteModelPickerRow
                key={model.id}
                model={model}
                checked={selectedSet.has(model.name)}
                order={-1}
                disabled={disabled}
                label={label}
                onToggle={handleToggle}
                priceRow={priceByName?.get(model.name)}
                currency={currency}
              />
            ))}
          </ul>
        </TooltipProvider>
      )}
      {selected.length > 0 ? (
        <p className="text-xs text-muted-foreground">已选：{selected.join(', ')}</p>
      ) : null}
    </section>
  )
}
