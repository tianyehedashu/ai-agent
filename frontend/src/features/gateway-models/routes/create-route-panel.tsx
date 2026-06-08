import { useCallback, useEffect, useMemo, useState } from 'react'

import type { GatewayModel, GatewayRouteCreateBody } from '@/api/gateway'
import type { GatewayTeam } from '@/api/gateway/teams'
import { Button } from '@/components/ui/button'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import type { RoutingStrategy } from '@/features/gateway-models/constants'
import {
  RouteFallbackModelPicker,
  RouteOrderedModelPicker,
} from '@/features/gateway-models/routes/route-model-pool'
import { RoutingStrategySelect } from '@/features/gateway-models/routes/routing-strategy-select'
import { excludeModelsFromList } from '@/features/gateway-models/utils'
import { GATEWAY_DISPLAY_CURRENCY } from '@/features/gateway-pricing/display-currency'
import { useGatewayModelPrices } from '@/features/gateway-pricing/use-gateway-model-prices'
import { GatewayTeamCombobox } from '@/features/gateway-teams/gateway-team-combobox'
import { ChevronDown, Loader2, Route } from '@/lib/lucide-icons'
import { cn } from '@/lib/utils'

const DEFAULT_STRATEGY: RoutingStrategy = 'simple-shuffle'

interface CreateRoutePanelProps {
  targetTeamId: string
  targetTeamLabel: string | null
  targetTeams: readonly GatewayTeam[]
  onTargetTeamChange: (teamId: string) => void
  pickerModels: readonly GatewayModel[]
  modelsLoading?: boolean
  onSubmit: (body: GatewayRouteCreateBody) => void
  onCancel: () => void
  isSubmitting?: boolean
}

export function CreateRoutePanel({
  targetTeamId,
  targetTeamLabel,
  targetTeams,
  onTargetTeamChange,
  pickerModels,
  modelsLoading = false,
  onSubmit,
  onCancel,
  isSubmitting = false,
}: CreateRoutePanelProps): React.JSX.Element {
  const { byName: priceByName } = useGatewayModelPrices(GATEWAY_DISPLAY_CURRENCY)
  const [virtualModel, setVirtualModel] = useState('')
  const [primaryModels, setPrimaryModels] = useState<string[]>([])
  const [fallbacksGeneral, setFallbacksGeneral] = useState<string[]>([])
  const [fallbacksContentPolicy, setFallbacksContentPolicy] = useState<string[]>([])
  const [fallbacksContextWindow, setFallbacksContextWindow] = useState<string[]>([])
  const [strategy, setStrategy] = useState<RoutingStrategy>(DEFAULT_STRATEGY)
  const [advancedOpen, setAdvancedOpen] = useState(false)
  const selectableModelNames = useMemo(
    () => new Set(pickerModels.map((model) => model.name)),
    [pickerModels]
  )
  const hasTargetTeam =
    targetTeamId.length > 0 && targetTeams.some((team) => team.id === targetTeamId)

  const keepSelectableModels = useCallback(
    (names: string[]): string[] => {
      if (names.every((name) => selectableModelNames.has(name))) return names
      return names.filter((name) => selectableModelNames.has(name))
    },
    [selectableModelNames]
  )

  useEffect(() => {
    setPrimaryModels(keepSelectableModels)
    setFallbacksGeneral(keepSelectableModels)
    setFallbacksContentPolicy(keepSelectableModels)
    setFallbacksContextWindow(keepSelectableModels)
  }, [keepSelectableModels])

  const setPrimaryModelsAndPruneFallbacks = useCallback((next: string[]): void => {
    setPrimaryModels(next)
    setFallbacksGeneral((prev) => excludeModelsFromList(prev, next))
    setFallbacksContentPolicy((prev) => excludeModelsFromList(prev, next))
    setFallbacksContextWindow((prev) => excludeModelsFromList(prev, next))
  }, [])

  const canSubmit =
    hasTargetTeam &&
    virtualModel.trim().length > 0 &&
    primaryModels.length > 0 &&
    !isSubmitting &&
    !modelsLoading

  function handleSubmit(): void {
    if (!canSubmit) return
    onSubmit({
      virtual_model: virtualModel.trim(),
      primary_models: primaryModels,
      fallbacks_general: excludeModelsFromList(fallbacksGeneral, primaryModels),
      fallbacks_content_policy: excludeModelsFromList(fallbacksContentPolicy, primaryModels),
      fallbacks_context_window: excludeModelsFromList(fallbacksContextWindow, primaryModels),
      strategy,
    })
  }

  return (
    <div className="flex min-h-0 flex-col rounded-lg border bg-card">
      <div className="border-b p-4">
        <p className="flex flex-wrap items-center gap-2 text-base font-semibold">
          <Route className="h-4 w-4" aria-hidden="true" />
          新建虚拟路由
          {targetTeamLabel ? (
            <span className="max-w-full truncate rounded bg-muted px-1.5 py-0.5 text-[10px] font-normal text-muted-foreground">
              {targetTeamLabel}
            </span>
          ) : null}
        </p>
        <p className="mt-1 text-sm text-muted-foreground">
          配置对外暴露的 <span className="font-mono">model</span> 名、主模型池与 Router 策略
        </p>
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        <div className="space-y-2">
          <Label>所属团队</Label>
          <GatewayTeamCombobox
            value={targetTeamId}
            onChange={onTargetTeamChange}
            teams={targetTeams}
            disabled={isSubmitting || targetTeams.length === 0}
            placeholder={targetTeams.length === 0 ? '无可创建路由的团队' : '选择团队'}
            className="h-10 w-full max-w-full justify-between text-sm"
            popoverContentClassName="min-w-[min(22rem,calc(100vw-1.5rem))]"
          />
          {targetTeams.length === 0 ? (
            <p className="text-[11px] text-destructive">当前账号没有可创建路由的团队。</p>
          ) : null}
        </div>

        <div>
          <Label>虚拟名（对外 model）</Label>
          <Input
            className="mt-1 font-mono"
            value={virtualModel}
            onChange={(e) => {
              setVirtualModel(e.target.value)
            }}
            placeholder="agent-default"
            disabled={isSubmitting}
          />
        </div>

        <section className="space-y-2">
          <Label className="text-xs font-semibold uppercase text-muted-foreground">
            Router 策略
          </Label>
          <RoutingStrategySelect
            value={strategy}
            onValueChange={setStrategy}
            disabled={isSubmitting}
          />
        </section>

        {!hasTargetTeam ? (
          <p className="text-sm text-muted-foreground">请选择所属团队后再配置模型。</p>
        ) : modelsLoading ? (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            正在加载可用模型…
          </p>
        ) : (
          <>
            <RouteOrderedModelPicker
              models={pickerModels}
              selected={primaryModels}
              onSelectedChange={setPrimaryModelsAndPruneFallbacks}
              disabled={isSubmitting}
              label="主模型（按优先级从上到下）"
              priceByName={priceByName}
              currency={GATEWAY_DISPLAY_CURRENCY}
            />

            <RouteFallbackModelPicker
              models={pickerModels}
              selected={fallbacksGeneral}
              onSelectedChange={setFallbacksGeneral}
              disabled={isSubmitting}
              label="通用 Fallback（可选）"
              description="主模型均失败时按顺序尝试"
              excludeNames={primaryModels}
              priceByName={priceByName}
              currency={GATEWAY_DISPLAY_CURRENCY}
            />

            <Collapsible open={advancedOpen} onOpenChange={setAdvancedOpen}>
              <CollapsibleTrigger asChild>
                <Button type="button" variant="ghost" size="sm" className="h-8 px-2 text-xs">
                  <ChevronDown
                    className={cn(
                      'mr-1 h-4 w-4 transition-transform',
                      advancedOpen && 'rotate-180'
                    )}
                  />
                  更多 Fallback 分组
                </Button>
              </CollapsibleTrigger>
              <CollapsibleContent className="mt-2 space-y-3">
                <div className="grid gap-3 sm:grid-cols-2">
                  <RouteFallbackModelPicker
                    models={pickerModels}
                    selected={fallbacksContentPolicy}
                    onSelectedChange={setFallbacksContentPolicy}
                    disabled={isSubmitting}
                    label="内容策略"
                    excludeNames={primaryModels}
                    priceByName={priceByName}
                    currency={GATEWAY_DISPLAY_CURRENCY}
                  />
                  <RouteFallbackModelPicker
                    models={pickerModels}
                    selected={fallbacksContextWindow}
                    onSelectedChange={setFallbacksContextWindow}
                    disabled={isSubmitting}
                    label="上下文窗口"
                    excludeNames={primaryModels}
                    priceByName={priceByName}
                    currency={GATEWAY_DISPLAY_CURRENCY}
                  />
                </div>
              </CollapsibleContent>
            </Collapsible>
          </>
        )}

        <div className="flex flex-wrap gap-2 pt-2">
          <Button type="button" variant="ghost" disabled={isSubmitting} onClick={onCancel}>
            取消
          </Button>
          <Button type="button" disabled={!canSubmit} onClick={handleSubmit}>
            {isSubmitting ? (
              <>
                <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                创建中…
              </>
            ) : (
              '创建'
            )}
          </Button>
        </div>
      </div>
    </div>
  )
}
