import { useCallback, useMemo, useState } from 'react'

import { Link } from 'react-router-dom'

import type { GatewayModel, GatewayRoute, GatewayRouteUpdateBody } from '@/api/gateway'
import { Alert, AlertDescription } from '@/components/ui/alert'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { routingStrategyLabel } from '@/features/gateway-models/constants'
import { PersonalRouteBatchPicker } from '@/features/gateway-models/routes/personal-route-batch-picker-lazy'
import { RouteModelBatchAddButton } from '@/features/gateway-models/routes/route-model-batch-picker-dialog'
import {
  RouteFallbackModelPicker,
  RouteOrderedModelPicker,
} from '@/features/gateway-models/routes/route-model-pool'
import { RoutingStrategySelect } from '@/features/gateway-models/routes/routing-strategy-select'
import { isWeightedRoutingStrategy } from '@/features/gateway-models/routes/routing-strategy-utils'
import {
  useDeploymentWeightDrafts,
  type DeploymentWeightChange,
} from '@/features/gateway-models/routes/use-deployment-weight-drafts'
import { excludeModelsFromList, stringArraysEqual } from '@/features/gateway-models/utils'
import { GATEWAY_DISPLAY_CURRENCY } from '@/features/gateway-pricing/display-currency'
import { useGatewayModelPrices } from '@/features/gateway-pricing/use-gateway-model-prices'
import { ChevronDown, Loader2 } from '@/lib/lucide-icons'
import { cn } from '@/lib/utils'

interface RouteTopologyEditorProps {
  route: GatewayRoute | null
  models: readonly GatewayModel[]
  pickerModels: readonly GatewayModel[]
  isSaving: boolean
  isDeleting?: boolean
  modelsLoading?: boolean
  teamLabel?: string | null
  readOnly?: boolean
  onSave: (
    id: string,
    body: GatewayRouteUpdateBody,
    weightChanges: readonly DeploymentWeightChange[]
  ) => void
  onDelete?: (id: string) => void
  allowPersonalBatchAdd?: boolean
}

interface RouteTopologyFormProps {
  route: GatewayRoute
  models: readonly GatewayModel[]
  pickerModels: readonly GatewayModel[]
  isSaving: boolean
  isDeleting?: boolean
  modelsLoading?: boolean
  teamLabel?: string | null
  readOnly?: boolean
  onSave: (
    id: string,
    body: GatewayRouteUpdateBody,
    weightChanges: readonly DeploymentWeightChange[]
  ) => void
  onDelete?: (id: string) => void
  allowPersonalBatchAdd?: boolean
}

function RouteTopologyForm({
  route,
  models,
  pickerModels,
  isSaving,
  isDeleting = false,
  modelsLoading = false,
  teamLabel,
  readOnly = false,
  onSave,
  onDelete,
  allowPersonalBatchAdd = false,
}: RouteTopologyFormProps): React.JSX.Element {
  const [batchOpen, setBatchOpen] = useState(false)
  const pricingTeamId = route.team_id ?? route.tenant_id ?? null
  const { byName: priceByName } = useGatewayModelPrices(GATEWAY_DISPLAY_CURRENCY, {
    teamId: pricingTeamId,
  })

  // readOnly 已由父组件基于路由所属团队角色判断（canManageTeamRoutes），
  // 无需再用 canWrite（基于当前工作区团队）做冗余检查——跨团队视图下二者可能不一致。
  const editable = !readOnly

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
  const { weightByName, setWeight, changes: weightDraftChanges } = useDeploymentWeightDrafts(models)

  const setPrimaryModelsAndPruneFallbacks = useCallback((next: string[]): void => {
    setPrimaryModels(next)
    setFallbacksGeneral((prev) => excludeModelsFromList(prev, next))
    setFallbacksContentPolicy((prev) => excludeModelsFromList(prev, next))
    setFallbacksContextWindow((prev) => excludeModelsFromList(prev, next))
  }, [])

  const handleBatchAdd = useCallback(
    (refs: string[]): void => {
      setPrimaryModelsAndPruneFallbacks([...new Set([...primaryModels, ...refs])])
    },
    [primaryModels, setPrimaryModelsAndPruneFallbacks]
  )

  const batchAddAction =
    editable && allowPersonalBatchAdd ? (
      <RouteModelBatchAddButton
        disabled={isSaving}
        onClick={() => {
          setBatchOpen(true)
        }}
      />
    ) : null

  const validationIssues = useMemo(() => {
    if (modelsLoading) return []
    const issues: string[] = []
    for (const name of primaryModels) {
      const m = modelsByName.get(name)
      if (!m) issues.push(`主模型「${name}」不可引用或已失效`)
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
    modelsLoading,
  ])

  const weightedMode = isWeightedRoutingStrategy(strategy)

  // 仅按权重路由且仍在主模型池内的权重草稿才会随保存提交
  const weightChanges = useMemo(
    () =>
      weightedMode
        ? weightDraftChanges.filter((change) => primaryModels.includes(change.modelName))
        : [],
    [weightedMode, weightDraftChanges, primaryModels]
  )

  const dirty =
    !stringArraysEqual(primaryModels, route.primary_models) ||
    strategy !== route.strategy ||
    enabled !== route.enabled ||
    !stringArraysEqual(fallbacksGeneral, route.fallbacks_general) ||
    !stringArraysEqual(fallbacksContentPolicy, route.fallbacks_content_policy) ||
    !stringArraysEqual(fallbacksContextWindow, route.fallbacks_context_window) ||
    weightChanges.length > 0

  function handleSave(): void {
    if (validationIssues.length > 0) return
    onSave(
      route.id,
      {
        primary_models: primaryModels,
        fallbacks_general: excludeModelsFromList(fallbacksGeneral, primaryModels),
        fallbacks_content_policy: excludeModelsFromList(fallbacksContentPolicy, primaryModels),
        fallbacks_context_window: excludeModelsFromList(fallbacksContextWindow, primaryModels),
        strategy,
        enabled,
      },
      weightChanges
    )
  }

  return (
    <div className="flex min-h-0 flex-col rounded-lg border bg-card">
      <div className="border-b p-4">
        <p className="flex flex-wrap items-center gap-2 font-mono text-base font-semibold">
          <span className="min-w-0 break-all">{route.virtual_model}</span>
          {teamLabel ? (
            <span className="max-w-full truncate rounded bg-muted px-1.5 py-0.5 font-sans text-[10px] font-normal text-muted-foreground">
              {teamLabel}
            </span>
          ) : null}
        </p>
        <p className="mt-1 text-sm text-muted-foreground">虚拟名 · 客户端请求 model 字段</p>
        <p className="mt-1 text-xs text-muted-foreground">
          策略：{routingStrategyLabel(strategy)}
          {dirty && strategy !== route.strategy ? (
            <span className="text-amber-600">（未保存）</span>
          ) : null}
        </p>
        {editable ? (
          <div className="mt-3 flex items-center gap-2">
            <Switch
              checked={enabled}
              onCheckedChange={setEnabled}
              aria-label={enabled ? '停用路由' : '启用路由'}
            />
            <span className="text-sm text-muted-foreground">{enabled ? '已启用' : '已禁用'}</span>
          </div>
        ) : (
          <p className="mt-2 text-xs text-muted-foreground">
            {route.source === 'system'
              ? '系统级路由，仅可查看；团队可创建同名路由覆盖。'
              : '当前账号无此团队路由编辑权限。'}
          </p>
        )}
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        <Alert>
          <AlertDescription className="text-sm">
            对外调用时，虚拟 Key 白名单需包含{' '}
            <span className="font-mono">{route.virtual_model}</span>（留空表示允许全部）。{' '}
            <Link to="/gateway/keys" className="text-primary underline-offset-4 hover:underline">
              管理虚拟 Key
            </Link>
          </AlertDescription>
        </Alert>
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
            disabled={!editable}
          />
        </section>

        <RouteOrderedModelPicker
          models={pickerModels}
          selected={primaryModels}
          onSelectedChange={setPrimaryModelsAndPruneFallbacks}
          disabled={!editable}
          label="主模型（按优先级从上到下）"
          priceByName={priceByName}
          currency={GATEWAY_DISPLAY_CURRENCY}
          showWeight={weightedMode}
          weightByName={weightByName}
          onWeightChange={editable ? setWeight : undefined}
          batchAddAction={batchAddAction}
        />
        {allowPersonalBatchAdd ? (
          <PersonalRouteBatchPicker
            open={batchOpen}
            onOpenChange={setBatchOpen}
            excludeNames={primaryModels}
            onConfirm={handleBatchAdd}
          />
        ) : null}

        {weightedMode ? (
          <p className="-mt-2 text-xs text-muted-foreground">
            按权重路由：主模型行内的 <span className="font-mono">w</span>{' '}
            字段修改后，点击「保存路由」生效（更新模型 weight）。
          </p>
        ) : null}

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
              disabled={!editable}
              label="通用 Fallback"
              description="主模型均失败时按顺序尝试"
              excludeNames={primaryModels}
              priceByName={priceByName}
              currency={GATEWAY_DISPLAY_CURRENCY}
            />
            <div className="grid gap-3 sm:grid-cols-2">
              <RouteFallbackModelPicker
                models={pickerModels}
                selected={fallbacksContentPolicy}
                onSelectedChange={setFallbacksContentPolicy}
                disabled={!editable}
                label="内容策略"
                excludeNames={primaryModels}
                priceByName={priceByName}
                currency={GATEWAY_DISPLAY_CURRENCY}
              />
              <RouteFallbackModelPicker
                models={pickerModels}
                selected={fallbacksContextWindow}
                onSelectedChange={setFallbacksContextWindow}
                disabled={!editable}
                label="上下文窗口"
                excludeNames={primaryModels}
                priceByName={priceByName}
                currency={GATEWAY_DISPLAY_CURRENCY}
              />
            </div>
          </CollapsibleContent>
        </Collapsible>

        {editable ? (
          <div className="flex flex-wrap items-center gap-2">
            <Button
              size="sm"
              disabled={!dirty || isSaving || validationIssues.length > 0}
              onClick={handleSave}
            >
              {isSaving ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : null}
              保存路由
            </Button>
            {onDelete ? (
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button
                    type="button"
                    size="sm"
                    variant="destructive"
                    disabled={isDeleting || isSaving}
                  >
                    {isDeleting ? <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" /> : null}
                    删除路由
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>删除虚拟路由？</AlertDialogTitle>
                    <AlertDialogDescription>
                      将永久删除「{route.virtual_model}」。引用此虚拟名的虚拟 Key 白名单需手动更新。
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>取消</AlertDialogCancel>
                    <AlertDialogAction
                      onClick={() => {
                        onDelete(route.id)
                      }}
                    >
                      确认删除
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            ) : null}
          </div>
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
  isDeleting,
  modelsLoading,
  teamLabel,
  readOnly: readOnlyProp = false,
  onSave,
  onDelete,
  allowPersonalBatchAdd = false,
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

  const readOnly = route.source === 'system' || readOnlyProp

  return (
    <RouteTopologyForm
      key={route.id}
      route={route}
      models={models}
      pickerModels={pickerModels}
      isSaving={isSaving}
      isDeleting={isDeleting}
      modelsLoading={modelsLoading}
      teamLabel={teamLabel}
      readOnly={readOnly}
      onSave={onSave}
      onDelete={readOnly ? undefined : onDelete}
      allowPersonalBatchAdd={allowPersonalBatchAdd}
    />
  )
}
