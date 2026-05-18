import { memo, useEffect, useMemo, useState } from 'react'

import { Copy, ExternalLink, Info, Loader2, Zap } from 'lucide-react'
import { Link } from 'react-router-dom'

import type {
  GatewayModel,
  GatewayModelRouteUsageItem,
  GatewayModelUpdateBody,
  GatewayRoute,
  ProviderCredential,
} from '@/api/gateway'
import { ModelStatusBadge } from '@/components/model-status-badge'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { TESTABLE_CAPABILITIES, NO_CREDENTIAL } from '@/features/gateway-models/constants'
import { credentialDetailHref } from '@/features/gateway-models/paths'
import {
  channelLabel,
  coalesceNumber,
  parsePositiveInt,
  routesReferencingModel,
} from '@/features/gateway-models/utils'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { cn } from '@/lib/utils'

import { ModelCapabilityBadges } from './model-capability-badges'

interface ModelInspectorProps {
  model: GatewayModel | null
  credentials: ProviderCredential[]
  routes: GatewayRoute[]
  usageDays: 1 | 7 | 30
  usageRow: GatewayModelRouteUsageItem | undefined
  usageLoading: boolean
  isTesting: boolean
  isSaving: boolean
  onTest: (id: string) => void
  onSave: (id: string, body: GatewayModelUpdateBody) => void
  onToggleEnabled: (id: string, enabled: boolean) => void
  emptyReason?: 'none' | 'filter'
  /** 无选中模型时的主/副文案（凭据详情等非侧栏场景） */
  emptyTitle?: string
  emptyDescription?: string
}

const ModelInspectorPanel = memo(function ModelInspectorPanel({
  model,
  credentials,
  routes,
  usageDays,
  usageRow,
  usageLoading,
  isTesting,
  isSaving,
  onTest,
  onSave,
  onToggleEnabled,
}: ModelInspectorProps & { model: GatewayModel }): React.JSX.Element {
  const { canWrite } = useGatewayPermission()
  const [usageScope, setUsageScope] = useState<'workspace' | 'user'>('workspace')
  const [modelName, setModelName] = useState(model.name)
  const [realModel, setRealModel] = useState(model.real_model)
  const [credentialId, setCredentialId] = useState(model.credential_id)
  const [weight, setWeight] = useState(String(model.weight))
  const [rpmLimit, setRpmLimit] = useState(model.rpm_limit !== null ? String(model.rpm_limit) : '')
  const [tpmLimit, setTpmLimit] = useState(model.tpm_limit !== null ? String(model.tpm_limit) : '')
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    setModelName(model.name)
    setRealModel(model.real_model)
    setCredentialId(model.credential_id)
    setWeight(String(model.weight))
    setRpmLimit(model.rpm_limit !== null ? String(model.rpm_limit) : '')
    setTpmLimit(model.tpm_limit !== null ? String(model.tpm_limit) : '')
  }, [
    model.id,
    model.name,
    model.real_model,
    model.credential_id,
    model.weight,
    model.rpm_limit,
    model.tpm_limit,
  ])

  const referencingRoutes = useMemo(
    () => routesReferencingModel(routes, model.name),
    [routes, model.name]
  )

  const credential = useMemo(
    () => credentials.find((c) => c.id === model.credential_id),
    [credentials, model.credential_id]
  )

  const credentialOptions = useMemo(() => {
    const pool = credentials.filter((c) => c.is_active || c.id === model.credential_id)
    const matching = pool.filter((c) => c.provider === model.provider)
    return matching.length > 0 ? matching : pool
  }, [credentials, model.credential_id, model.provider])

  const isTestable = TESTABLE_CAPABILITIES.has(model.capability)
  const slice = usageScope === 'workspace' ? usageRow?.workspace : usageRow?.user
  const req = slice?.requests ?? 0
  const tok = (slice?.input_tokens ?? 0) + (slice?.output_tokens ?? 0)
  const cost = coalesceNumber(slice?.cost_usd)
  const daysLabel = usageDays === 1 ? '24 小时' : usageDays === 7 ? '7 天' : '30 天'
  const nameDirty = modelName.trim() !== model.name
  const dirty =
    nameDirty ||
    realModel.trim() !== model.real_model ||
    credentialId !== model.credential_id ||
    weight !== String(model.weight) ||
    rpmLimit !== (model.rpm_limit !== null ? String(model.rpm_limit) : '') ||
    tpmLimit !== (model.tpm_limit !== null ? String(model.tpm_limit) : '')

  async function copyReason(): Promise<void> {
    const text = model.last_test_reason?.trim()
    if (!text) return
    await navigator.clipboard.writeText(text)
    setCopied(true)
    window.setTimeout(() => {
      setCopied(false)
    }, 2000)
  }

  function handleSave(): void {
    const trimmedName = modelName.trim()
    if (!trimmedName || !realModel.trim() || !credentialId) return
    const body: GatewayModelUpdateBody = {
      real_model: realModel.trim(),
      credential_id: credentialId,
      weight: parsePositiveInt(weight) ?? 1,
      rpm_limit: parsePositiveInt(rpmLimit),
      tpm_limit: parsePositiveInt(tpmLimit),
    }
    if (trimmedName !== model.name) {
      body.name = trimmedName
    }
    onSave(model.id, body)
  }

  return (
    <div className="flex min-h-0 flex-col rounded-lg border bg-card">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b p-4">
        <div className="min-w-0 flex-1">
          <p className="font-mono text-base font-semibold leading-tight">
            {nameDirty ? modelName.trim() || model.name : model.name}
          </p>
          <p className="mt-1 text-sm text-muted-foreground">{channelLabel(model.provider)}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <ModelStatusBadge
            status={model.last_test_status}
            testedAt={model.last_tested_at}
            reason={model.last_test_reason}
            entitlementStatus={model.entitlement_status}
            entitlementResetAt={model.entitlement_reset_at}
          />
          {canWrite ? (
            <>
              <Switch
                checked={model.enabled}
                disabled={isSaving}
                onCheckedChange={(checked) => {
                  onToggleEnabled(model.id, checked)
                }}
                aria-label={model.enabled ? '停用模型' : '启用模型'}
              />
              <Button
                size="sm"
                variant="outline"
                disabled={!isTestable || isTesting}
                onClick={() => {
                  onTest(model.id)
                }}
              >
                {isTesting ? (
                  <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Zap className="mr-1 h-3.5 w-3.5" />
                )}
                测试连通性
              </Button>
            </>
          ) : (
            <span className="text-xs text-muted-foreground">
              {model.enabled ? '已启用' : '已禁用'}
            </span>
          )}
        </div>
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        {model.last_test_status === 'failed' && model.last_test_reason ? (
          <Alert variant="destructive">
            <AlertTitle>连通性不可用</AlertTitle>
            <AlertDescription className="space-y-2">
              <pre className="max-h-40 overflow-auto whitespace-pre-wrap break-words font-mono text-xs">
                {model.last_test_reason}
              </pre>
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="h-7"
                onClick={() => void copyReason()}
              >
                <Copy className="mr-1 h-3 w-3" />
                {copied ? '已复制' : '复制错误'}
              </Button>
            </AlertDescription>
          </Alert>
        ) : null}

        <section className="space-y-2">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            能力
          </h3>
          <ModelCapabilityBadges model={model} />
        </section>

        <section className="space-y-3">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            配置
          </h3>
          <p className="text-xs text-muted-foreground">
            对外 API 与虚拟 Key 白名单使用「注册别名」；实际上游厂商模型由「上游模型 ID」决定。
          </p>
          <TooltipProvider delayDuration={0}>
            {nameDirty && referencingRoutes.length > 0 ? (
              <Alert>
                <AlertTitle>将同步更新虚拟路由引用</AlertTitle>
                <AlertDescription>
                  保存后，下列虚拟路由中的模型名将自动从「{model.name}」改为「
                  {modelName.trim() || '…'}」。
                </AlertDescription>
              </Alert>
            ) : null}
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="sm:col-span-2">
                <div className="mb-1 flex items-center gap-1">
                  <Label className="text-xs">注册别名</Label>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <button type="button" aria-label="注册别名说明" className="inline-flex">
                        <Info className="h-3.5 w-3.5 text-muted-foreground" />
                      </button>
                    </TooltipTrigger>
                    <TooltipContent className="max-w-xs text-xs">
                      客户端请求里的 model 名称；与 LiteLLM 上游 id 无关，勿与 dashscope/qwen-max
                      这类厂商串混淆。
                    </TooltipContent>
                  </Tooltip>
                </div>
                <Input
                  className="mt-0 font-mono text-sm"
                  value={modelName}
                  readOnly={!canWrite}
                  onChange={(e) => {
                    setModelName(e.target.value)
                  }}
                />
              </div>
              <div className="sm:col-span-2">
                <div className="mb-1 flex items-center gap-1">
                  <Label className="text-xs">上游模型 ID</Label>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <button type="button" aria-label="上游模型 ID 说明" className="inline-flex">
                        <Info className="h-3.5 w-3.5 text-muted-foreground" />
                      </button>
                    </TooltipTrigger>
                    <TooltipContent className="max-w-xs text-xs">
                      可填短 id（如 qwen-max），保存时由服务端按当前行的 provider 拼成 LiteLLM
                      全称；若已含 /（如 dashscope/qwen-max），则原样保存，且前缀须与 provider
                      一致。
                    </TooltipContent>
                  </Tooltip>
                </div>
                <Input
                  className="mt-0 font-mono text-sm"
                  value={realModel}
                  readOnly={!canWrite}
                  onChange={(e) => {
                    setRealModel(e.target.value)
                  }}
                />
                <p className="mt-1 text-xs text-muted-foreground">
                  保存后列表与 LiteLLM 路由以服务端规范化后的值为准。
                </p>
              </div>
              <div className="sm:col-span-2">
                <Label className="text-xs">凭据</Label>
                {canWrite ? (
                  <Select
                    value={credentialId || NO_CREDENTIAL}
                    onValueChange={(v) => {
                      setCredentialId(v === NO_CREDENTIAL ? '' : v)
                    }}
                  >
                    <SelectTrigger className="mt-1">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {credentialOptions.map((c) => (
                        <SelectItem key={c.id} value={c.id}>
                          {c.name} · {c.provider}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                ) : (
                  <p className="mt-1 text-sm">{credential?.name ?? model.credential_id}</p>
                )}
                {credential ? (
                  <Link
                    to={credentialDetailHref(credential.id)}
                    className="mt-1 inline-flex items-center gap-1 text-xs text-primary underline-offset-4 hover:underline"
                  >
                    凭据详情 <ExternalLink className="h-3 w-3" />
                  </Link>
                ) : null}
              </div>
              <div>
                <Label className="text-xs">权重</Label>
                <Input
                  className="mt-1 tabular-nums"
                  inputMode="numeric"
                  value={weight}
                  readOnly={!canWrite}
                  onChange={(e) => {
                    setWeight(e.target.value)
                  }}
                />
              </div>
              <div>
                <Label className="text-xs">每分钟请求 / 令牌</Label>
                <div className="mt-1 grid grid-cols-2 gap-2">
                  <Input
                    inputMode="numeric"
                    placeholder="∞"
                    value={rpmLimit}
                    readOnly={!canWrite}
                    onChange={(e) => {
                      setRpmLimit(e.target.value)
                    }}
                  />
                  <Input
                    inputMode="numeric"
                    placeholder="∞"
                    value={tpmLimit}
                    readOnly={!canWrite}
                    onChange={(e) => {
                      setTpmLimit(e.target.value)
                    }}
                  />
                </div>
              </div>
            </div>
            {canWrite ? (
              <Button
                size="sm"
                className="mt-1"
                disabled={
                  !dirty || isSaving || !modelName.trim() || !realModel.trim() || !credentialId
                }
                onClick={handleSave}
              >
                {isSaving ? '保存中…' : '保存配置'}
              </Button>
            ) : null}
          </TooltipProvider>
        </section>

        <section className="space-y-2">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            用量 · {daysLabel}
          </h3>
          <div className="flex w-fit gap-1 rounded-md border bg-background p-0.5">
            {(['workspace', 'user'] as const).map((scope) => (
              <Button
                key={scope}
                type="button"
                size="sm"
                variant={usageScope === scope ? 'default' : 'ghost'}
                className="h-7 px-2 text-xs"
                onClick={() => {
                  setUsageScope(scope)
                }}
              >
                {scope === 'workspace' ? '工作区' : '账号'}
              </Button>
            ))}
          </div>
          {usageLoading ? (
            <p className="text-sm text-muted-foreground">加载用量…</p>
          ) : (
            <p className="text-sm tabular-nums">
              {req} 次 · {tok} tokens · ${cost.toFixed(4)} USD
            </p>
          )}
          <Link
            to={
              model.credential_id
                ? `/gateway/logs?credential_id=${encodeURIComponent(model.credential_id)}`
                : '/gateway/logs'
            }
            className="inline-flex items-center gap-1 text-xs text-primary underline-offset-4 hover:underline"
          >
            在调用日志中查看 <ExternalLink className="h-3 w-3" />
          </Link>
        </section>

        <section className="space-y-2">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            虚拟路由引用
          </h3>
          {referencingRoutes.length === 0 ? (
            <p className="text-sm text-muted-foreground">暂无虚拟路由引用此别名</p>
          ) : (
            <ul className="space-y-1">
              {referencingRoutes.map((r) => (
                <li key={r.id}>
                  <Link
                    to={`/gateway/routes?routeId=${encodeURIComponent(r.id)}`}
                    className={cn(
                      'inline-flex items-center gap-1 font-mono text-sm text-primary underline-offset-4 hover:underline'
                    )}
                  >
                    {r.virtual_model}
                    <ExternalLink className="h-3 w-3" />
                  </Link>
                </li>
              ))}
            </ul>
          )}
          <Link
            to="/gateway/routes"
            className="text-xs text-muted-foreground underline-offset-4 hover:underline"
          >
            管理虚拟路由
          </Link>
        </section>
      </div>
    </div>
  )
})

export const ModelInspector = memo(function ModelInspector({
  model,
  credentials,
  routes,
  usageDays,
  usageRow,
  usageLoading,
  isTesting,
  isSaving,
  onTest,
  onSave,
  onToggleEnabled,
  emptyReason = 'none',
  emptyTitle,
  emptyDescription,
}: ModelInspectorProps): React.JSX.Element {
  if (!model) {
    const title =
      emptyTitle ?? (emptyReason === 'filter' ? '当前筛选无匹配模型' : '选择左侧模型查看详情')
    const description =
      emptyDescription ??
      (emptyReason === 'filter'
        ? '请调整搜索或健康筛选，或从左侧列表选择模型。'
        : '可在此编辑注册别名与上游配置、查看健康状态、用量与被哪些虚拟路由引用。')

    return (
      <div className="rounded-lg border border-dashed bg-muted/10 px-6 py-10 text-center">
        <p className="text-sm font-medium text-foreground">{title}</p>
        <p className="mx-auto mt-1 max-w-sm text-sm text-muted-foreground">{description}</p>
      </div>
    )
  }

  return (
    <ModelInspectorPanel
      key={model.id}
      model={model}
      credentials={credentials}
      routes={routes}
      usageDays={usageDays}
      usageRow={usageRow}
      usageLoading={usageLoading}
      isTesting={isTesting}
      isSaving={isSaving}
      onTest={onTest}
      onSave={onSave}
      onToggleEnabled={onToggleEnabled}
    />
  )
})
