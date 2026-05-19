import { useCallback, useState } from 'react'

import type { GatewayModel, GatewayRouteCreateBody } from '@/api/gateway'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import type { RoutingStrategy } from '@/features/gateway-models/constants'
import {
  RouteFallbackModelPicker,
  RouteOrderedModelPicker,
} from '@/features/gateway-models/routes/route-model-pool'
import { RoutingStrategySelect } from '@/features/gateway-models/routes/routing-strategy-select'
import { excludeModelsFromList } from '@/features/gateway-models/utils'
import { useGatewayModelPrices } from '@/features/gateway-pricing/use-gateway-model-prices'
import { Loader2, Route } from '@/lib/lucide-icons'
import { useUserPreferenceStore } from '@/stores/user-preference'

const DEFAULT_STRATEGY: RoutingStrategy = 'simple-shuffle'

interface CreateRoutePanelProps {
  pickerModels: readonly GatewayModel[]
  modelsLoading?: boolean
  onSubmit: (body: GatewayRouteCreateBody) => void
  onCancel: () => void
  isSubmitting?: boolean
}

export function CreateRoutePanel({
  pickerModels,
  modelsLoading = false,
  onSubmit,
  onCancel,
  isSubmitting = false,
}: CreateRoutePanelProps): React.JSX.Element {
  const displayCurrency = useUserPreferenceStore((s) => s.displayCurrency)
  const { byName: priceByName } = useGatewayModelPrices(displayCurrency)
  const [virtualModel, setVirtualModel] = useState('')
  const [primaryModels, setPrimaryModels] = useState<string[]>([])
  const [fallbacksGeneral, setFallbacksGeneral] = useState<string[]>([])
  const [strategy, setStrategy] = useState<RoutingStrategy>(DEFAULT_STRATEGY)

  const setPrimaryModelsAndPruneFallbacks = useCallback((next: string[]): void => {
    setPrimaryModels(next)
    setFallbacksGeneral((prev) => excludeModelsFromList(prev, next))
  }, [])

  const canSubmit =
    virtualModel.trim().length > 0 && primaryModels.length > 0 && !isSubmitting && !modelsLoading

  function handleSubmit(): void {
    if (!canSubmit) return
    onSubmit({
      virtual_model: virtualModel.trim(),
      primary_models: primaryModels,
      fallbacks_general: excludeModelsFromList(fallbacksGeneral, primaryModels),
      strategy,
    })
  }

  return (
    <div className="flex min-h-0 flex-col rounded-lg border bg-card">
      <div className="border-b p-4">
        <p className="flex items-center gap-2 text-base font-semibold">
          <Route className="h-4 w-4" aria-hidden="true" />
          新建虚拟路由
        </p>
        <p className="mt-1 text-sm text-muted-foreground">
          配置对外暴露的 <span className="font-mono">model</span> 名、主模型池与 Router 策略
        </p>
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto p-4">
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

        {modelsLoading ? (
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
              currency={displayCurrency}
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
              currency={displayCurrency}
            />
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
