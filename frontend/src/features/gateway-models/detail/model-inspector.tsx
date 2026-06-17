import { memo, useEffect, useMemo, useState } from 'react'

import { useSearchParams } from 'react-router-dom'

import type {
  GatewayModel,
  GatewayModelRouteUsageItem,
  GatewayModelUpdateBody,
  GatewayRoute,
  GatewayUsageAggregation,
  ProviderCredential,
} from '@/api/gateway'
import type { PersonalGatewayModelUpdateBody } from '@/api/gateway/my-models'
import { ModelStatusBadge } from '@/components/model-status-badge'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
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
import { credentialSummaryLabel } from '@/features/gateway-credentials/credential-summary-display'
import { useGatewayCredentialDirectory } from '@/features/gateway-credentials/use-credential-directory'
import {
  NO_CREDENTIAL,
  parseModelsScopeTab,
  TESTABLE_CAPABILITIES,
} from '@/features/gateway-models/constants'
import { ModelDetailPricingSection } from '@/features/gateway-models/detail/model-detail-pricing-section'
import { ModelDetailQuotaSection } from '@/features/gateway-models/detail/model-detail-quota-section'
import {
  canDeleteGatewayModel,
  canDeletePersonalGatewayModel,
  canManageGatewayModel,
  canManagePersonalGatewayModel,
  canResyncGatewayModelCapabilities,
  isConfigManagedSystemModel,
} from '@/features/gateway-models/gateway-model-permissions'
import {
  channelLabel,
  coalesceNumber,
  parsePositiveInt,
  routesReferencingModel,
} from '@/features/gateway-models/utils'
import { UsageAggregationToggle } from '@/features/gateway-usage/usage-aggregation-toggle'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useGatewayTeamId } from '@/hooks/use-gateway-team-id'
import { Copy, Info, Loader2, Play, RefreshCw, Trash2 } from '@/lib/lucide-icons'
import { copyToClipboard } from '@/lib/utils'
import { useCurrentUser } from '@/stores/user'

import {
  ModelCapabilityEditor,
  capabilityEditorValuesFromModel,
  capabilityEditorValuesFromPersonalModel,
  modelCapabilityPatchFromEditor,
  type ModelCapabilityEditorValues,
} from '../model-capability-editor'
import { ModelCapabilityBadges } from '../team/model-capability-badges'

import type { PersonalModelInspectorContext } from '../personal/personal-model-inspector-adapter'

export type ModelInspectorScope = 'team' | 'personal'

interface ModelInspectorProps {
  model: GatewayModel | null
  scope?: ModelInspectorScope
  personalContext?: PersonalModelInspectorContext
  credentials: ProviderCredential[]
  routes: GatewayRoute[]
  usageDays: 1 | 7 | 30
  usageRow: GatewayModelRouteUsageItem | undefined
  usageLoading: boolean
  isTesting: boolean
  isSaving: boolean
  isResyncing?: boolean
  isDeleting?: boolean
  onTest: (id: string) => void
  onSave?: (id: string, body: GatewayModelUpdateBody) => void
  onSavePersonal?: (id: string, body: PersonalGatewayModelUpdateBody) => void
  onResyncCapabilities?: (id: string) => void
  onToggleEnabled: (id: string, enabled: boolean) => void
  onDelete?: (id: string) => void
  emptyReason?: 'none' | 'filter'
  /** 无选中模型时的主/副文案（凭据详情等非侧栏场景） */
  emptyTitle?: string
  emptyDescription?: string
}

const ModelInspectorPanel = memo(function ModelInspectorPanel({
  model,
  scope = 'team',
  personalContext,
  credentials,
  routes,
  usageDays,
  usageRow,
  usageLoading,
  isTesting,
  isSaving,
  isResyncing = false,
  isDeleting = false,
  onTest,
  onSave,
  onSavePersonal,
  onResyncCapabilities,
  onToggleEnabled,
  onDelete,
}: ModelInspectorProps & { model: GatewayModel }): React.JSX.Element {
  const teamId = useGatewayTeamId()
  const [searchParams] = useSearchParams()
  const { canWrite, canContribute, isAdmin, isPlatformAdmin, isPlatformViewer } =
    useGatewayPermission()
  const currentUser = useCurrentUser()
  const viewerUserId = currentUser?.id ?? null
  const hasAuthSession = currentUser !== null
  const isPersonal = scope === 'personal'
  const scopeTab = parseModelsScopeTab(searchParams.get('tab'))
  const permissionContext = useMemo(() => ({ preferSystem: scopeTab === 'system' }), [scopeTab])
  const canManage = isPersonal
    ? canManagePersonalGatewayModel(personalContext?.userId, viewerUserId, hasAuthSession)
    : canManageGatewayModel(model, viewerUserId, canWrite, isPlatformAdmin, permissionContext)
  const canDelete = isPersonal
    ? canDeletePersonalGatewayModel(personalContext?.userId, viewerUserId, hasAuthSession)
    : canDeleteGatewayModel(model, viewerUserId, canWrite, isPlatformAdmin, permissionContext)
  const configManaged = isPersonal ? false : isConfigManagedSystemModel(model, permissionContext)
  const canResync =
    !configManaged &&
    (isPersonal
      ? canManagePersonalGatewayModel(personalContext?.userId, viewerUserId, hasAuthSession)
      : canResyncGatewayModelCapabilities(
          model,
          viewerUserId,
          canWrite,
          isPlatformAdmin,
          permissionContext
        ))
  const { byId: credentialSummariesById } = useGatewayCredentialDirectory()
  const [usageScope, setUsageScope] = useState<GatewayUsageAggregation>('workspace')
  const [modelName, setModelName] = useState(model.name)
  const [displayName, setDisplayName] = useState(personalContext?.displayName ?? '')
  const [realModel, setRealModel] = useState(model.real_model)
  const [credentialId, setCredentialId] = useState(model.credential_id)
  const [weight, setWeight] = useState(String(model.weight))
  const [rpmLimit, setRpmLimit] = useState(model.rpm_limit !== null ? String(model.rpm_limit) : '')
  const [tpmLimit, setTpmLimit] = useState(model.tpm_limit !== null ? String(model.tpm_limit) : '')
  const [copied, setCopied] = useState(false)
  const [capabilityValues, setCapabilityValues] = useState<ModelCapabilityEditorValues>(() =>
    isPersonal
      ? capabilityEditorValuesFromPersonalModel({
          capability: model.capability,
          model_types: model.model_types,
          upstream_call_shape: model.upstream_call_shape,
          selector_capabilities: model.selector_capabilities,
          tags: model.tags,
        })
      : capabilityEditorValuesFromModel(model)
  )
  const [capabilityBaseline, setCapabilityBaseline] = useState<ModelCapabilityEditorValues>(() =>
    isPersonal
      ? capabilityEditorValuesFromPersonalModel({
          capability: model.capability,
          model_types: model.model_types,
          upstream_call_shape: model.upstream_call_shape,
          selector_capabilities: model.selector_capabilities,
          tags: model.tags,
        })
      : capabilityEditorValuesFromModel(model)
  )

  useEffect(() => {
    setModelName(model.name)
    setDisplayName(personalContext?.displayName ?? '')
    setRealModel(model.real_model)
    setCredentialId(model.credential_id)
    setWeight(String(model.weight))
    setRpmLimit(model.rpm_limit !== null ? String(model.rpm_limit) : '')
    setTpmLimit(model.tpm_limit !== null ? String(model.tpm_limit) : '')
    const capValues = isPersonal
      ? capabilityEditorValuesFromPersonalModel({
          capability: model.capability,
          model_types: model.model_types,
          upstream_call_shape: model.upstream_call_shape,
          selector_capabilities: model.selector_capabilities,
          tags: model.tags,
        })
      : capabilityEditorValuesFromModel(model)
    setCapabilityValues(capValues)
    setCapabilityBaseline(capValues)
  }, [
    isPersonal,
    model.id,
    model.name,
    model.real_model,
    model.credential_id,
    model.weight,
    model.rpm_limit,
    model.tpm_limit,
    model.capability,
    model.model_types,
    model.upstream_call_shape,
    model.tags,
    model.selector_capabilities,
    personalContext?.displayName,
  ])

  const referencingRoutes = useMemo(
    () => routesReferencingModel(routes, model.name),
    [routes, model.name]
  )

  const credentialSummary = credentialSummariesById.get(model.credential_id)

  const credentialOptions = useMemo(() => {
    const pool = credentials.filter((c) => c.is_active || c.id === model.credential_id)
    const matching = pool.filter((c) => c.provider === model.provider)
    return matching.length > 0 ? matching : pool
  }, [credentials, model.credential_id, model.provider])

  const isTestable = TESTABLE_CAPABILITIES.has(capabilityValues.capability)
  const testButtonLabel = model.last_test_status !== null ? '重新测试' : '测试连通性'
  const slice = usageScope === 'workspace' ? usageRow?.workspace : usageRow?.user
  const req = slice?.requests ?? 0
  const tok = (slice?.input_tokens ?? 0) + (slice?.output_tokens ?? 0)
  const cost = coalesceNumber(slice?.cost_usd)
  const daysLabel = usageDays === 1 ? '24 小时' : usageDays === 7 ? '7 天' : '30 天'
  const nameDirty = !isPersonal && modelName.trim() !== model.name
  const displayNameDirty =
    isPersonal && displayName.trim() !== (personalContext?.displayName ?? '').trim()
  const capabilityPatch = modelCapabilityPatchFromEditor(capabilityValues, capabilityBaseline)
  const capabilityDirty = Object.keys(capabilityPatch).length > 0
  const dirty =
    nameDirty ||
    displayNameDirty ||
    realModel.trim() !== model.real_model ||
    credentialId !== model.credential_id ||
    (!isPersonal &&
      (weight !== String(model.weight) ||
        rpmLimit !== (model.rpm_limit !== null ? String(model.rpm_limit) : '') ||
        tpmLimit !== (model.tpm_limit !== null ? String(model.tpm_limit) : ''))) ||
    capabilityDirty

  async function copyReason(): Promise<void> {
    const text = model.last_test_reason?.trim()
    if (!text) return
    await copyToClipboard(text)
    setCopied(true)
    window.setTimeout(() => {
      setCopied(false)
    }, 2000)
  }

  function handleSave(): void {
    const trimmedName = modelName.trim()
    if (!realModel.trim() || !credentialId) return

    if (isPersonal) {
      const trimmedDisplayName = displayName.trim()
      if (!trimmedDisplayName) return
      const body: PersonalGatewayModelUpdateBody = {
        display_name: trimmedDisplayName,
        model_id: realModel.trim(),
        credential_id: credentialId,
      }
      if (capabilityPatch.model_types) {
        body.model_types = capabilityPatch.model_types
      }
      onSavePersonal?.(model.id, body)
      return
    }

    if (!trimmedName) return
    if (
      capabilityPatch.capability !== undefined &&
      referencingRoutes.length > 0 &&
      !window.confirm(
        `该模型被 ${String(referencingRoutes.length)} 条虚拟路由引用；修改主调用面须与路由内其他 deployment 一致。是否继续保存？`
      )
    ) {
      return
    }
    const body: GatewayModelUpdateBody = {
      real_model: realModel.trim(),
      credential_id: credentialId,
      weight: parsePositiveInt(weight) ?? 1,
      rpm_limit: parsePositiveInt(rpmLimit),
      tpm_limit: parsePositiveInt(tpmLimit),
      ...capabilityPatch,
    }
    if (trimmedName !== model.name) {
      body.name = trimmedName
    }
    onSave?.(model.id, body)
  }

  return (
    <TooltipProvider delayDuration={0}>
      <div className="flex min-h-0 flex-col rounded-lg border bg-card">
        <div className="flex flex-wrap items-start justify-between gap-3 border-b p-4">
          <div className="min-w-0 flex-1">
            {isPersonal ? (
              <>
                <p className="text-base font-semibold leading-tight">
                  {displayNameDirty
                    ? displayName.trim() || personalContext?.displayName
                    : personalContext?.displayName}
                </p>
                <p className="mt-1 font-mono text-sm text-muted-foreground">{model.name}</p>
              </>
            ) : (
              <p className="font-mono text-base font-semibold leading-tight">
                {nameDirty ? modelName.trim() || model.name : model.name}
              </p>
            )}
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
            {canManage ? (
              <>
                <Switch
                  checked={model.enabled}
                  disabled={isSaving}
                  onCheckedChange={(checked) => {
                    onToggleEnabled(model.id, checked)
                  }}
                  aria-label={model.enabled ? '停用模型' : '启用模型'}
                />
                {isTestable ? (
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={isTesting || isSaving}
                    onClick={() => {
                      onTest(model.id)
                    }}
                  >
                    {isTesting ? (
                      <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Play className="mr-1 h-3.5 w-3.5" />
                    )}
                    {testButtonLabel}
                  </Button>
                ) : null}
                {canResync && onResyncCapabilities ? (
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={isResyncing || isSaving}
                    onClick={() => {
                      onResyncCapabilities(model.id)
                    }}
                  >
                    {isResyncing ? (
                      <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <RefreshCw className="mr-1 h-3.5 w-3.5" />
                    )}
                    从 LiteLLM 同步能力
                  </Button>
                ) : null}
                {onDelete ? (
                  configManaged || !canDelete ? (
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <span tabIndex={0}>
                          <Button
                            size="sm"
                            variant="outline"
                            className="text-destructive/50"
                            disabled
                          >
                            <Trash2 className="mr-1 h-3.5 w-3.5" />
                            删除
                          </Button>
                        </span>
                      </TooltipTrigger>
                      <TooltipContent className="max-w-xs text-xs">
                        配置同步托管的系统模型不可删除；请通过 gateway-catalog 或配置管理
                      </TooltipContent>
                    </Tooltip>
                  ) : (
                    <Button
                      size="sm"
                      variant="outline"
                      className="text-destructive hover:text-destructive"
                      disabled={isDeleting || isSaving}
                      onClick={() => {
                        onDelete(model.id)
                      }}
                    >
                      {isDeleting ? (
                        <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <Trash2 className="mr-1 h-3.5 w-3.5" />
                      )}
                      删除
                    </Button>
                  )
                ) : null}
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
                <div className="flex flex-wrap gap-2">
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
                  {isTestable ? (
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      className="h-7"
                      disabled={isTesting}
                      onClick={() => {
                        onTest(model.id)
                      }}
                    >
                      {isTesting ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : null}
                      {testButtonLabel}
                    </Button>
                  ) : null}
                </div>
              </AlertDescription>
            </Alert>
          ) : null}

          <section className="space-y-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                能力
              </h3>
              {canResync && onResyncCapabilities ? (
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="h-7 text-xs"
                  disabled={isResyncing || isSaving}
                  onClick={() => {
                    onResyncCapabilities(model.id)
                  }}
                >
                  {isResyncing ? (
                    <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                  ) : (
                    <RefreshCw className="mr-1 h-3 w-3" />
                  )}
                  从 LiteLLM 同步
                </Button>
              ) : null}
            </div>
            {canManage && !configManaged ? (
              <ModelCapabilityEditor
                values={capabilityValues}
                onChange={setCapabilityValues}
                hideUpstreamCallShape={isPersonal}
                hideThinkingParam={isPersonal}
              />
            ) : (
              <ModelCapabilityBadges model={model} />
            )}
          </section>

          <ModelDetailPricingSection model={model} scope={scope} teamId={teamId} />

          {currentUser?.id ? (
            <ModelDetailQuotaSection
              model={model}
              scope={scope}
              teamId={teamId}
              userId={currentUser.id}
              isAdmin={isAdmin}
              canManageQuota={
                !isPlatformViewer &&
                (isPersonal
                  ? canManagePersonalGatewayModel(
                      personalContext?.userId,
                      viewerUserId,
                      hasAuthSession
                    )
                  : canWrite || canContribute)
              }
            />
          ) : null}

          <section className="space-y-3">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              配置
            </h3>
            <p className="text-xs text-muted-foreground">
              对外 API 与虚拟 Key 白名单使用「注册别名」；实际上游厂商模型由「上游模型 ID」决定。
            </p>
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
              {isPersonal ? (
                <div className="sm:col-span-2">
                  <Label className="text-xs">显示名</Label>
                  <Input
                    className="mt-1 text-sm"
                    value={displayName}
                    readOnly={!canManage}
                    onChange={(e) => {
                      setDisplayName(e.target.value)
                    }}
                  />
                </div>
              ) : null}
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
                  readOnly={!canManage || isPersonal}
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
                  readOnly={!canManage}
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
                {credentialSummary?.scope === 'system' ? (
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    该模型由平台维护，凭据由平台管理员管理。
                  </p>
                ) : null}
                {canManage ? (
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
                  <div className="mt-1 flex flex-wrap items-center gap-2">
                    <p className="text-sm">
                      {credentialSummaryLabel(credentialSummary, model.credential_id)}
                    </p>
                    {credentialSummary?.scope === 'system' ? (
                      <Badge variant="secondary" className="text-[10px] font-normal">
                        系统全局
                      </Badge>
                    ) : null}
                    {!credentialSummary?.is_active ? (
                      <Badge variant="outline" className="text-[10px] font-normal">
                        已停用
                      </Badge>
                    ) : null}
                  </div>
                )}
              </div>
              {!isPersonal ? (
                <>
                  <div>
                    <Label className="text-xs">权重</Label>
                    <Input
                      className="mt-1 tabular-nums"
                      inputMode="numeric"
                      value={weight}
                      readOnly={!canManage}
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
                        readOnly={!canManage}
                        onChange={(e) => {
                          setRpmLimit(e.target.value)
                        }}
                      />
                      <Input
                        inputMode="numeric"
                        placeholder="∞"
                        value={tpmLimit}
                        readOnly={!canManage}
                        onChange={(e) => {
                          setTpmLimit(e.target.value)
                        }}
                      />
                    </div>
                  </div>
                </>
              ) : null}
            </div>
            {canManage ? (
              <Button
                size="sm"
                className="mt-1"
                disabled={
                  !dirty ||
                  isSaving ||
                  !realModel.trim() ||
                  !credentialId ||
                  (isPersonal ? !displayName.trim() : !modelName.trim())
                }
                onClick={handleSave}
              >
                {isSaving ? '保存中…' : '保存配置'}
              </Button>
            ) : null}
          </section>

          <section className="space-y-2">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              用量 · {daysLabel}
            </h3>
            <UsageAggregationToggle value={usageScope} size="compact" onChange={setUsageScope} />
            {usageLoading ? (
              <p className="text-sm text-muted-foreground">加载用量…</p>
            ) : (
              <p className="text-sm tabular-nums">
                {req} 次 · {tok} tokens · ${cost.toFixed(4)} USD
              </p>
            )}
          </section>

          {!isPersonal ? (
            <section className="space-y-2">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                虚拟路由引用
              </h3>
              {referencingRoutes.length === 0 ? (
                <p className="text-sm text-muted-foreground">暂无虚拟路由引用此别名</p>
              ) : (
                <ul className="space-y-1">
                  {referencingRoutes.map((r) => (
                    <li key={r.id} className="font-mono text-sm text-muted-foreground">
                      {r.virtual_model}
                    </li>
                  ))}
                </ul>
              )}
            </section>
          ) : null}
        </div>
      </div>
    </TooltipProvider>
  )
})

export const ModelInspector = memo(function ModelInspector({
  model,
  scope = 'team',
  personalContext,
  credentials,
  routes,
  usageDays,
  usageRow,
  usageLoading,
  isTesting,
  isSaving,
  isResyncing = false,
  isDeleting = false,
  onTest,
  onSave,
  onSavePersonal,
  onResyncCapabilities,
  onToggleEnabled,
  onDelete,
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
      scope={scope}
      personalContext={personalContext}
      model={model}
      credentials={credentials}
      routes={routes}
      usageDays={usageDays}
      usageRow={usageRow}
      usageLoading={usageLoading}
      isTesting={isTesting}
      isSaving={isSaving}
      isResyncing={isResyncing}
      isDeleting={isDeleting}
      onTest={onTest}
      onSave={onSave}
      onSavePersonal={onSavePersonal}
      onResyncCapabilities={onResyncCapabilities}
      onToggleEnabled={onToggleEnabled}
      onDelete={onDelete}
    />
  )
})
