import { memo, useCallback, useMemo, useRef } from 'react'

import { Link } from 'react-router-dom'

import type { GatewayModel, MyPriceRow } from '@/api/gateway'
import { ModelStatusBadge } from '@/components/model-status-badge'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { TooltipProvider } from '@/components/ui/tooltip'
import { RouteModelAddCombobox } from '@/features/gateway-models/routes/route-model-add-combobox'
import {
  moveOrderedModelList,
  toggleModelSet,
  toggleOrderedModelList,
} from '@/features/gateway-models/utils'
import { GATEWAY_DISPLAY_CURRENCY } from '@/features/gateway-pricing/display-currency'
import { PricingBadge } from '@/features/gateway-pricing/pricing-badge'
import { ChevronDown, ChevronUp, X } from '@/lib/lucide-icons'
import { cn } from '@/lib/utils'
import type { DisplayCurrency } from '@/types/money'

const PICKER_ROW_CV = '[contain-intrinsic-size:auto_2.75rem] [content-visibility:auto]' as const

function buildModelsByName(models: readonly GatewayModel[]): Map<string, GatewayModel> {
  return new Map(models.map((m) => [m.name, m]))
}

function resolveSelectedModels(
  selected: readonly string[],
  modelsByName: ReadonlyMap<string, GatewayModel>
): GatewayModel[] {
  const resolved: GatewayModel[] = []
  for (const name of selected) {
    const model = modelsByName.get(name)
    if (model !== undefined) resolved.push(model)
  }
  return resolved
}

interface RouteSelectedModelRowProps {
  model: GatewayModel
  order: number
  disabled: boolean
  showOrderControls?: boolean
  selectedCount?: number
  onMove?: (order: number, dir: -1 | 1) => void
  onRemove: (name: string) => void
  priceRow?: MyPriceRow
  currency?: DisplayCurrency
}

const RouteSelectedModelRow = memo(function RouteSelectedModelRow({
  model,
  order,
  disabled,
  showOrderControls = false,
  selectedCount = 0,
  onMove,
  onRemove,
  priceRow,
  currency = GATEWAY_DISPLAY_CURRENCY,
}: RouteSelectedModelRowProps): React.JSX.Element {
  return (
    <li
      className={cn(PICKER_ROW_CV, 'flex items-center gap-2 rounded px-1 py-1 hover:bg-muted/30')}
    >
      {showOrderControls ? (
        <span className="w-5 shrink-0 text-center text-xs tabular-nums text-muted-foreground">
          {order + 1}
        </span>
      ) : null}
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
      {showOrderControls && !disabled && onMove ? (
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
            disabled={order >= selectedCount - 1}
            onClick={() => {
              onMove(order, 1)
            }}
            aria-label="下移"
          >
            <ChevronDown className="h-4 w-4" />
          </Button>
        </div>
      ) : null}
      {!disabled ? (
        <Button
          type="button"
          size="icon"
          variant="ghost"
          className="h-7 w-7 shrink-0 text-muted-foreground hover:text-foreground"
          onClick={() => {
            onRemove(model.name)
          }}
          aria-label={`移除 ${model.name}`}
        >
          <X className="h-4 w-4" />
        </Button>
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
  const modelsByName = useMemo(() => buildModelsByName(models), [models])
  const selectedSet = useMemo(() => new Set(selected), [selected])
  const selectedRef = useRef(selected)
  selectedRef.current = selected
  const onSelectedChangeRef = useRef(onSelectedChange)
  onSelectedChangeRef.current = onSelectedChange

  const selectedModels = useMemo(
    () => resolveSelectedModels(selected, modelsByName),
    [selected, modelsByName]
  )

  const unselectedCandidates = useMemo(
    () => models.filter((m) => !selectedSet.has(m.name)),
    [models, selectedSet]
  )

  const handleAdd = useCallback((name: string): void => {
    onSelectedChangeRef.current(toggleOrderedModelList(selectedRef.current, name, true))
  }, [])

  const handleRemove = useCallback((name: string): void => {
    onSelectedChangeRef.current(toggleOrderedModelList(selectedRef.current, name, false))
  }, [])

  const handleMove = useCallback((order: number, dir: -1 | 1): void => {
    onSelectedChangeRef.current(moveOrderedModelList(selectedRef.current, order, dir))
  }, [])

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
        <TooltipProvider delayDuration={200}>
          {selectedModels.length === 0 ? (
            <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed bg-muted/10 px-4 py-8 text-center">
              <p className="text-sm text-muted-foreground">尚未配置主模型</p>
              {!disabled ? (
                <RouteModelAddCombobox
                  candidates={unselectedCandidates}
                  onPick={handleAdd}
                  triggerLabel="添加主模型"
                  priceByName={priceByName}
                  currency={currency}
                />
              ) : null}
            </div>
          ) : (
            <>
              <ul className="space-y-1 rounded-md border p-2">
                {selectedModels.map((model, index) => (
                  <RouteSelectedModelRow
                    key={model.id}
                    model={model}
                    order={index}
                    disabled={disabled}
                    showOrderControls={showOrderControls}
                    selectedCount={selectedModels.length}
                    onMove={showOrderControls && !disabled ? handleMove : undefined}
                    onRemove={handleRemove}
                    priceRow={priceByName?.get(model.name)}
                    currency={currency}
                  />
                ))}
              </ul>
              {!disabled ? (
                <RouteModelAddCombobox
                  candidates={unselectedCandidates}
                  onPick={handleAdd}
                  triggerLabel="添加主模型"
                  variant="ghost"
                  priceByName={priceByName}
                  currency={currency}
                />
              ) : null}
            </>
          )}
        </TooltipProvider>
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
  const modelsByName = useMemo(() => buildModelsByName(models), [models])
  const selectedSet = useMemo(() => new Set(selected), [selected])
  const selectedRef = useRef(selected)
  selectedRef.current = selected
  const onSelectedChangeRef = useRef(onSelectedChange)
  onSelectedChangeRef.current = onSelectedChange

  const { poolCandidates, unselectedCandidates } = useMemo(() => {
    const pool: GatewayModel[] = []
    const unselected: GatewayModel[] = []
    for (const model of models) {
      if (exclude.has(model.name)) continue
      pool.push(model)
      if (!selectedSet.has(model.name)) unselected.push(model)
    }
    return { poolCandidates: pool, unselectedCandidates: unselected }
  }, [models, exclude, selectedSet])

  const selectedModels = useMemo(
    () => resolveSelectedModels(selected, modelsByName),
    [selected, modelsByName]
  )

  const handleAdd = useCallback((name: string): void => {
    onSelectedChangeRef.current(toggleModelSet(selectedRef.current, name, true))
  }, [])

  const handleRemove = useCallback((name: string): void => {
    onSelectedChangeRef.current(toggleModelSet(selectedRef.current, name, false))
  }, [])

  const noPool = poolCandidates.length === 0

  return (
    <section className="space-y-2">
      <div>
        <Label className="text-xs">{label}</Label>
        {description ? <p className="mt-0.5 text-xs text-muted-foreground">{description}</p> : null}
      </div>
      {noPool ? (
        <p className="text-sm text-muted-foreground">暂无可选模型（请先配置主模型或注册模型）</p>
      ) : (
        <TooltipProvider delayDuration={200}>
          {selectedModels.length === 0 ? (
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-sm text-muted-foreground">尚未配置</p>
              {!disabled ? (
                <RouteModelAddCombobox
                  candidates={unselectedCandidates}
                  onPick={handleAdd}
                  triggerLabel="添加 Fallback"
                  priceByName={priceByName}
                  currency={currency}
                />
              ) : null}
            </div>
          ) : (
            <>
              <ul className="space-y-1 rounded-md border p-2">
                {selectedModels.map((model) => (
                  <RouteSelectedModelRow
                    key={model.id}
                    model={model}
                    order={-1}
                    disabled={disabled}
                    onRemove={handleRemove}
                    priceRow={priceByName?.get(model.name)}
                    currency={currency}
                  />
                ))}
              </ul>
              {!disabled ? (
                <RouteModelAddCombobox
                  candidates={unselectedCandidates}
                  onPick={handleAdd}
                  triggerLabel="添加 Fallback"
                  variant="ghost"
                  priceByName={priceByName}
                  currency={currency}
                />
              ) : null}
            </>
          )}
        </TooltipProvider>
      )}
    </section>
  )
}
