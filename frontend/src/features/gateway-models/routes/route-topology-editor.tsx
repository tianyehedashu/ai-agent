import { useCallback, useMemo, useState } from 'react'

import type { GatewayModel, GatewayRoute, GatewayRouteUpdateBody } from '@/api/gateway'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { routingStrategyLabel } from '@/features/gateway-models/constants'
import {
  RouteFallbackModelPicker,
  RouteOrderedModelPicker,
} from '@/features/gateway-models/routes/route-model-pool'
import { RoutingStrategySelect } from '@/features/gateway-models/routes/routing-strategy-select'
import { excludeModelsFromList, stringArraysEqual } from '@/features/gateway-models/utils'
import { useGatewayModelPrices } from '@/features/gateway-pricing/use-gateway-model-prices'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { ChevronDown, Loader2 } from '@/lib/lucide-icons'
import { cn } from '@/lib/utils'
import { useUserPreferenceStore } from '@/stores/user-preference'

interface RouteTopologyEditorProps {
  route: GatewayRoute | null
  models: GatewayModel[]
  pickerModels: readonly GatewayModel[]
  isSaving: boolean
  onSave: (id: string, body: GatewayRouteUpdateBody) => void
}

interface RouteTopologyFormProps {
  route: GatewayRoute
  models: GatewayModel[]
  pickerModels: readonly GatewayModel[]
  isSaving: boolean
  onSave: (id: string, body: GatewayRouteUpdateBody) => void
}

function RouteTopologyForm({
  route,
  models,
  pickerModels,
  isSaving,
  onSave,
}: RouteTopologyFormProps): React.JSX.Element {
  const { canWrite } = useGatewayPermission()
  const displayCurrency = useUserPreferenceStore((s) => s.displayCurrency)
  const { byName: priceByName } = useGatewayModelPrices(displayCurrency)

  const modelsByName = useMemo(() => new Map(models.map((m) => [m.name, m])), [models])
  const registeredNames = useMemo(() => new Set(models.map((m) => m.name)), [models])

  const [primaryModels, setPrimaryModels] = useState(() => [...route.primary_models])
  const [strategy, setStrategy] = useState<string>(() => route.strategy)
  const [enabled, setEnabled] = useState(() => route.enabled)
  const [fallbacksGeneral, setFallbacksGeneral] = useState(() => [...route.fallbacks_general])
  const [fallbacksContentPolicy, setFallbacksContentPolicy] = useState(() => [
    ...route.fallbacks_content_policy,
  ])
  const [fallbacksContextWindow, setFallbacksContextWindow] = useState(() => [
    ...route.fallbacks_context_window,
  ])
  const [advancedOpen, setAdvancedOpen] = useState(false)

  const setPrimaryModelsAndPruneFallbacks = useCallback((next: string[]): void => {
    setPrimaryModels(next)
    setFallbacksGeneral((prev) => excludeModelsFromList(prev, next))
    setFallbacksContentPolicy((prev) => excludeModelsFromList(prev, next))
    setFallbacksContextWindow((prev) => excludeModelsFromList(prev, next))
  }, [])

  const validationIssues = useMemo(() => {
    const issues: string[] = []
    for (const name of primaryModels) {
      const m = modelsByName.get(name)
      if (!m) issues.push(`主模型「${name}」未注册`)
      else if (!m.enabled) issues.push(`主模型「${name}」已禁用`)
    }
    for (const name of fallbacksGeneral) {
      if (!registeredNames.has(name)) issues.push(`Fallback「${name}」未注册`)
    }
    for (const name of fallbacksContentPolicy) {
      if (!registeredNames.has(name)) issues.push(`内容策略 Fallback「${name}」未注册`)
    }
    for (const name of fallbacksContextWindow) {
      if (!registeredNames.has(name)) issues.push(`上下文窗口 Fallback「${name}」未注册`)
    }
    if (primaryModels.length === 0) issues.push('至少选择一个主模型')
    return issues
  }, [
    primaryModels,
    fallbacksGeneral,
    fallbacksContentPolicy,
    fallbacksContextWindow,
    modelsByName,
    registeredNames,
  ])

  const dirty =
    !stringArraysEqual(primaryModels, route.primary_models) ||
    strategy !== route.strategy ||
    enabled !== route.enabled ||
    !stringArraysEqual(fallbacksGeneral, route.fallbacks_general) ||
    !stringArraysEqual(fallbacksContentPolicy, route.fallbacks_content_policy) ||
    !stringArraysEqual(fallbacksContextWindow, route.fallbacks_context_window)

  function handleSave(): void {
    if (validationIssues.length > 0) return
    onSave(route.id, {
      primary_models: primaryModels,
      fallbacks_general: excludeModelsFromList(fallbacksGeneral, primaryModels),
      fallbacks_content_policy: excludeModelsFromList(fallbacksContentPolicy, primaryModels),
      fallbacks_context_window: excludeModelsFromList(fallbacksContextWindow, primaryModels),
      strategy,
      enabled,
    })
  }

  return (
    <div className="flex min-h-0 flex-col rounded-lg border bg-card">
      <div className="border-b p-4">
        <p className="font-mono text-base font-semibold">{route.virtual_model}</p>
        <p className="mt-1 text-sm text-muted-foreground">虚拟名 · 客户端请求 model 字段</p>
        <p className="mt-1 text-xs text-muted-foreground">
          策略：{routingStrategyLabel(strategy)}
          {dirty && strategy !== route.strategy ? (
            <span className="text-amber-600">（未保存）</span>
          ) : null}
        </p>
        {canWrite ? (
          <div className="mt-3 flex items-center gap-2">
            <Switch
              checked={enabled}
              onCheckedChange={setEnabled}
              aria-label={enabled ? '停用路由' : '启用路由'}
            />
            <span className="text-sm text-muted-foreground">{enabled ? '已启用' : '已禁用'}</span>
          </div>
        ) : null}
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        {validationIssues.length > 0 ? (
          <Alert variant="destructive">
            <AlertDescription>
              <ul className="list-disc pl-4 text-sm">
                {validationIssues.map((issue) => (
                  <li key={issue}>{issue}</li>
                ))}
              </ul>
            </AlertDescription>
          </Alert>
        ) : null}

        <section className="space-y-2">
          <Label className="text-xs font-semibold uppercase text-muted-foreground">
            Router 策略
          </Label>
          <RoutingStrategySelect
            value={strategy}
            onValueChange={setStrategy}
            disabled={!canWrite}
          />
        </section>

        <RouteOrderedModelPicker
          models={pickerModels}
          selected={primaryModels}
          onSelectedChange={setPrimaryModelsAndPruneFallbacks}
          disabled={!canWrite}
          label="主模型（按优先级从上到下）"
          priceByName={priceByName}
          currency={displayCurrency}
        />

        <Collapsible open={advancedOpen} onOpenChange={setAdvancedOpen}>
          <CollapsibleTrigger asChild>
            <Button type="button" variant="ghost" size="sm" className="h-8 px-2 text-xs">
              <ChevronDown
                className={cn('mr-1 h-4 w-4 transition-transform', advancedOpen && 'rotate-180')}
              />
              Fallback 分组
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent className="mt-2 space-y-3">
            <RouteFallbackModelPicker
              models={pickerModels}
              selected={fallbacksGeneral}
              onSelectedChange={setFallbacksGeneral}
              disabled={!canWrite}
              label="通用 Fallback"
              description="主模型均失败时按顺序尝试"
              excludeNames={primaryModels}
              priceByName={priceByName}
              currency={displayCurrency}
            />
            <div className="grid gap-3 sm:grid-cols-2">
              <RouteFallbackModelPicker
                models={pickerModels}
                selected={fallbacksContentPolicy}
                onSelectedChange={setFallbacksContentPolicy}
                disabled={!canWrite}
                label="内容策略"
                excludeNames={primaryModels}
                priceByName={priceByName}
                currency={displayCurrency}
              />
              <RouteFallbackModelPicker
                models={pickerModels}
                selected={fallbacksContextWindow}
                onSelectedChange={setFallbacksContextWindow}
                disabled={!canWrite}
                label="上下文窗口"
                excludeNames={primaryModels}
                priceByName={priceByName}
                currency={displayCurrency}
              />
            </div>
          </CollapsibleContent>
        </Collapsible>

        {canWrite ? (
          <Button
            size="sm"
            disabled={!dirty || isSaving || validationIssues.length > 0}
            onClick={handleSave}
          >
            {isSaving ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : null}
            保存路由
          </Button>
        ) : null}
      </div>
    </div>
  )
}

export function RouteTopologyEditor({
  route,
  models,
  pickerModels,
  isSaving,
  onSave,
}: RouteTopologyEditorProps): React.JSX.Element {
  if (!route) {
    return (
      <div className="flex min-h-[320px] flex-col items-center justify-center rounded-lg border border-dashed bg-muted/10 p-8 text-center">
        <p className="text-sm font-medium">选择左侧虚拟路由</p>
        <p className="mt-1 max-w-sm text-sm text-muted-foreground">
          配置对外暴露的 model 名、主模型池与 Router 策略。
        </p>
      </div>
    )
  }

  return (
    <RouteTopologyForm
      key={route.id}
      route={route}
      models={models}
      pickerModels={pickerModels}
      isSaving={isSaving}
      onSave={onSave}
    />
  )
}
