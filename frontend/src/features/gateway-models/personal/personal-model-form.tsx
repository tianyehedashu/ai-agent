import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { Link } from 'react-router-dom'

import type { CredentialProbeResult, PersonalGatewayModel } from '@/api/gateway'
import { Button } from '@/components/ui/button'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { credentialProbeCacheKey } from '@/features/gateway-credentials/credential-probe-cache'
import { CredentialUpstreamModelsPanel } from '@/features/gateway-credentials/credential-upstream-models-panel'
import { providerLabel } from '@/features/gateway-credentials/provider-schemas'
import { NO_CREDENTIAL } from '@/features/gateway-models/constants'
import {
  ModelCapabilityEditor,
  capabilityEditorValuesFromPersonalModel,
  type ModelCapabilityEditorValues,
} from '@/features/gateway-models/model-capability-editor'
import { personalCredentialsIndexHref } from '@/features/gateway-models/paths'
import { useGatewayTeamId } from '@/hooks/use-gateway-team-id'
import { ChevronDown, Info, Loader2, RefreshCw } from '@/lib/lucide-icons'
import { cn } from '@/lib/utils'
import type { ModelType } from '@/types/user-model'

import { personalModelFormValuesFromModel } from './personal-model-form-values'

export interface PersonalModelFormValues {
  display_name: string
  provider: string
  model_id: string
  credential_id: string
  model_types: ModelType[]
  resync_capabilities?: boolean
  /** 思考模式（创建时可通过 tags 传递；编辑时 API 不支持 tags） */
  thinkingParam?: string
}

const EMPTY_FORM: PersonalModelFormValues = {
  display_name: '',
  provider: 'openai',
  model_id: '',
  credential_id: '',
  model_types: ['text'],
}

interface PersonalCredentialOption {
  id: string
  name: string
  provider: string
  is_active: boolean
}

interface PersonalModelFormProps {
  mode: 'create' | 'edit'
  credentials: PersonalCredentialOption[]
  initial?: PersonalGatewayModel | null
  onSubmit: (values: PersonalModelFormValues) => void
  onCancel: () => void
  isSubmitting: boolean
  /** 锁定为当前凭据（隐藏凭据下拉） */
  lockCredentialId?: string
  /** URL 深链预选凭据 */
  initialCredentialId?: string
  /** 批量导入成功 */
  onImported?: (createdCount: number, modelIds?: string[]) => void
  onResyncCapabilities?: () => void
  isResyncing?: boolean
}

function buildInitialForm(
  initial: PersonalGatewayModel | null | undefined,
  credentials: PersonalCredentialOption[],
  lockCredentialId?: string,
  initialCredentialId?: string
): PersonalModelFormValues {
  if (initial) return personalModelFormValuesFromModel(initial)
  const credId = lockCredentialId ?? initialCredentialId ?? ''
  const cred = credentials.find((c) => c.id === credId)
  return {
    ...EMPTY_FORM,
    credential_id: credId,
    provider: cred?.provider ?? EMPTY_FORM.provider,
  }
}

export function PersonalModelForm({
  mode,
  credentials,
  initial = null,
  onSubmit,
  onCancel,
  isSubmitting,
  lockCredentialId,
  initialCredentialId,
  onImported,
  onResyncCapabilities,
  isResyncing = false,
}: PersonalModelFormProps): React.JSX.Element {
  const teamId = useGatewayTeamId()
  const lockCredential = lockCredentialId !== undefined && lockCredentialId !== ''
  const activeCredentials = useMemo(() => credentials.filter((c) => c.is_active), [credentials])
  const credentialOptions = useMemo(() => {
    if (lockCredential) {
      return credentials.filter((c) => c.id === lockCredentialId || c.is_active)
    }
    return activeCredentials.length > 0 ? activeCredentials : credentials
  }, [activeCredentials, credentials, lockCredential, lockCredentialId])

  const [form, setForm] = useState<PersonalModelFormValues>(() =>
    buildInitialForm(initial, credentials, lockCredentialId, initialCredentialId)
  )
  const [capabilityValues, setCapabilityValues] = useState<ModelCapabilityEditorValues>(() =>
    initial && mode === 'edit'
      ? capabilityEditorValuesFromPersonalModel(initial)
      : capabilityEditorValuesFromPersonalModel({ capability: 'chat', model_types: ['text'] })
  )

  useEffect(() => {
    if (mode !== 'edit' || !initial) return
    setCapabilityValues(capabilityEditorValuesFromPersonalModel(initial))
  }, [mode, initial])
  const [manualOpen, setManualOpen] = useState(false)
  const [probeUnsupported, setProbeUnsupported] = useState(false)
  const manualSectionRef = useRef<HTMLDivElement>(null)
  const modelIdInputRef = useRef<HTMLInputElement>(null)

  const selectedCredential = useMemo(
    () => credentials.find((c) => c.id === form.credential_id),
    [credentials, form.credential_id]
  )

  const probeCacheKey = useMemo(
    () =>
      form.credential_id
        ? credentialProbeCacheKey('user', form.credential_id)
        : (['gateway', 'credential-probe', 'user', ''] as const),
    [form.credential_id]
  )

  useEffect(() => {
    if (mode !== 'create') return
    const credId = lockCredentialId ?? initialCredentialId ?? ''
    if (credId === '') return
    const cred = credentials.find((c) => c.id === credId)
    if (!cred) return
    setForm((prev) => ({
      ...prev,
      credential_id: credId,
      provider: cred.provider,
    }))
  }, [mode, lockCredentialId, initialCredentialId, credentials])

  const handleCredentialChange = useCallback(
    (credentialId: string): void => {
      const nextId = credentialId === NO_CREDENTIAL ? '' : credentialId
      const credential = credentials.find((c) => c.id === nextId)
      setProbeUnsupported(false)
      setForm((prev) => ({
        ...prev,
        credential_id: nextId,
        provider: credential?.provider ?? prev.provider,
        model_id: '',
      }))
    },
    [credentials]
  )

  const handleProbeResult = useCallback((result: CredentialProbeResult): void => {
    if (result.support === 'unsupported') {
      setProbeUnsupported(true)
      setManualOpen(true)
      window.requestAnimationFrame(() => {
        modelIdInputRef.current?.focus()
        manualSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
      })
    } else {
      setProbeUnsupported(false)
    }
  }, [])

  const handlePickUpstreamModelId = useCallback((upstreamId: string): void => {
    setForm((prev) => ({ ...prev, model_id: upstreamId }))
    setManualOpen(true)
    window.requestAnimationFrame(() => {
      modelIdInputRef.current?.focus()
      manualSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    })
  }, [])

  function handleSubmit(): void {
    if (mode === 'edit') {
      onSubmit({
        ...form,
        model_types:
          capabilityValues.modelTypes.length > 0 ? capabilityValues.modelTypes : form.model_types,
      })
      return
    }
    onSubmit({
      ...form,
      model_types:
        capabilityValues.modelTypes.length > 0 ? capabilityValues.modelTypes : form.model_types,
      thinkingParam: capabilityValues.thinkingParam,
    })
  }

  const title = mode === 'create' ? '添加个人模型' : '编辑模型'
  const descCreate = '选择个人凭据后，可从上游一键导入多个模型；也可在下方手动注册单条。'
  const descEdit = '修改模型配置与能力'

  if (mode === 'edit') {
    return (
      <TooltipProvider delayDuration={0}>
        <div className="mx-auto max-w-lg space-y-4 rounded-lg border bg-card p-6">
          <div>
            <h3 className="text-lg font-semibold">{title}</h3>
            <p className="mt-1 text-sm text-muted-foreground">{descEdit}</p>
          </div>

          <div className="grid gap-4">
            <div className="grid gap-1.5">
              <Label>名称 *</Label>
              <Input
                placeholder="如：我的 GPT-4o"
                value={form.display_name}
                onChange={(e) => {
                  setForm({ ...form, display_name: e.target.value })
                }}
              />
            </div>

            <div className="grid gap-1.5">
              <Label>提供商 *</Label>
              <Input className="font-mono text-sm" value={form.provider} readOnly disabled />
            </div>

            <div className="grid gap-1.5">
              <div className="flex items-center gap-1">
                <Label>模型 ID *</Label>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <button type="button" aria-label="模型 ID 说明" className="inline-flex">
                      <Info className="h-3.5 w-3.5 text-muted-foreground" />
                    </button>
                  </TooltipTrigger>
                  <TooltipContent className="max-w-xs text-xs">
                    可填短 id（如 qwen-max）或带厂商前缀的 LiteLLM 串；服务端会按所选 provider
                    规范化后再写入。
                  </TooltipContent>
                </Tooltip>
              </div>
              <Input
                placeholder="gpt-4o-mini, qwen-max"
                value={form.model_id}
                onChange={(e) => {
                  setForm({ ...form, model_id: e.target.value })
                }}
              />
            </div>

            <div className="grid gap-1.5">
              <Label>凭据 *</Label>
              <Select
                value={form.credential_id || NO_CREDENTIAL}
                onValueChange={(v) => {
                  setForm({ ...form, credential_id: v === NO_CREDENTIAL ? '' : v })
                }}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={NO_CREDENTIAL}>未选择</SelectItem>
                  {credentialOptions.map((c) => (
                    <SelectItem key={c.id} value={c.id}>
                      {c.name} · {c.provider}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <ModelCapabilityEditor
              values={capabilityValues}
              onChange={setCapabilityValues}
              hideUpstreamCallShape
              hideThinkingParam
              hideContextWindow
            />

            {onResyncCapabilities ? (
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={isSubmitting || isResyncing}
                onClick={onResyncCapabilities}
              >
                {isResyncing ? (
                  <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
                ) : (
                  <RefreshCw className="mr-1 h-3.5 w-3.5" />
                )}
                同步模型能力
              </Button>
            ) : null}
          </div>

          <div className="flex justify-end gap-2">
            <Button variant="outline" type="button" onClick={onCancel}>
              取消
            </Button>
            <Button type="button" onClick={handleSubmit} disabled={isSubmitting}>
              保存
            </Button>
          </div>
        </div>
      </TooltipProvider>
    )
  }

  if (activeCredentials.length === 0) {
    return (
      <div className="mx-auto max-w-2xl rounded-lg border border-dashed bg-muted/10 p-8">
        <h3 className="text-lg font-semibold">添加个人模型</h3>
        <p className="mt-2 text-sm text-muted-foreground">
          尚无已启用的个人凭据，请先到{' '}
          <Link
            to={personalCredentialsIndexHref(teamId)}
            className="text-primary underline-offset-4 hover:underline"
          >
            凭据管理
          </Link>{' '}
          添加并启用 API Key，再回来从上游导入或手动注册模型。
        </p>
        <Button variant="outline" size="sm" className="mt-4" onClick={onCancel}>
          返回模型列表
        </Button>
      </div>
    )
  }

  const credentialReady = form.credential_id !== ''
  const credentialActive = selectedCredential?.is_active ?? false
  const showProbePanel = credentialReady && credentialActive && !probeUnsupported

  return (
    <TooltipProvider delayDuration={0}>
      <div className="mx-auto max-w-2xl space-y-6">
        <div>
          <h3 className="text-lg font-semibold">{title}</h3>
          <p className="mt-1 text-sm text-muted-foreground">{descCreate}</p>
        </div>

        <section className="space-y-3 rounded-lg border bg-card p-4">
          <div className="space-y-1">
            <Label>步骤 1 · 选择凭据 *</Label>
            <p className="text-xs text-muted-foreground">提供商将跟随所选凭据，无需单独选择。</p>
          </div>
          {lockCredential ? (
            <div>
              <p className="text-sm">
                {selectedCredential?.name ?? form.credential_id}
                <span className="ml-2 font-mono text-xs text-muted-foreground">
                  ({providerLabel(form.provider)} · {form.provider})
                </span>
              </p>
            </div>
          ) : (
            <Select
              value={form.credential_id || NO_CREDENTIAL}
              onValueChange={handleCredentialChange}
            >
              <SelectTrigger>
                <SelectValue placeholder="选择个人凭据" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={NO_CREDENTIAL}>未选择</SelectItem>
                {credentialOptions.map((c) => (
                  <SelectItem key={c.id} value={c.id}>
                    {c.name} · {c.provider}
                    {!c.is_active ? '（已禁用）' : ''}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        </section>

        {credentialReady && !credentialActive ? (
          <div
            role="status"
            className="rounded-md border border-amber-500/30 bg-amber-500/5 px-4 py-3 text-sm text-amber-900 dark:text-amber-200"
          >
            <p className="font-medium">凭据已禁用</p>
            <p className="mt-1 text-muted-foreground">请先启用凭据后再探测上游或添加模型。</p>
            <Button type="button" variant="link" className="mt-2 h-auto p-0" asChild>
              <Link to={personalCredentialsIndexHref(teamId)}>前往凭据管理</Link>
            </Button>
          </div>
        ) : null}

        {showProbePanel ? (
          <section className="space-y-3 rounded-lg border bg-card p-4">
            <div>
              <h4 className="text-sm font-medium">步骤 2 · 从上游导入（推荐）</h4>
              <p className="mt-1 text-xs text-muted-foreground">
                探测上游可用模型，多选后一键批量导入。
              </p>
            </div>
            <CredentialUpstreamModelsPanel
              scope="user"
              credentialId={form.credential_id}
              provider={form.provider}
              embedded
              autoProbe
              cacheKey={probeCacheKey}
              onProbeResult={handleProbeResult}
              onImported={onImported}
              onPickModelId={handlePickUpstreamModelId}
            />
          </section>
        ) : null}

        {credentialReady && credentialActive && probeUnsupported ? (
          <div
            role="status"
            className="rounded-md border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-sm text-amber-900 dark:text-amber-200"
          >
            此提供商不支持自动列举模型，请在下方手动填写上游模型 ID。
          </div>
        ) : null}

        <Collapsible
          open={manualOpen}
          onOpenChange={setManualOpen}
          className="rounded-lg border bg-card"
        >
          <CollapsibleTrigger asChild>
            <Button
              variant="ghost"
              type="button"
              className="flex h-auto w-full items-center justify-between px-4 py-3 text-left"
            >
              <span>
                <span className="text-sm font-medium">手动添加单条</span>
                <span className="mt-0.5 block text-xs font-normal text-muted-foreground">
                  自定义展示名、模型类型，或 provider 不支持自动列举时使用
                </span>
              </span>
              <ChevronDown
                className={cn(
                  'ml-2 h-4 w-4 shrink-0 opacity-60 transition-transform',
                  manualOpen && 'rotate-180'
                )}
              />
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent ref={manualSectionRef} className="border-t px-4 pb-4 pt-3">
            <div className="grid gap-4">
              <div className="grid gap-1.5">
                <Label>名称 *</Label>
                <Input
                  placeholder="如：我的 GPT-4o"
                  value={form.display_name}
                  onChange={(e) => {
                    setForm({ ...form, display_name: e.target.value })
                  }}
                />
              </div>

              <div className="grid gap-1.5 sm:grid-cols-2">
                <div>
                  <Label>提供商</Label>
                  <Input
                    className="mt-1 font-mono text-sm"
                    value={form.provider}
                    readOnly
                    disabled={credentialReady}
                  />
                </div>
                <div>
                  <div className="flex items-center gap-1">
                    <Label>模型 ID *</Label>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <button type="button" aria-label="模型 ID 说明" className="inline-flex">
                          <Info className="h-3.5 w-3.5 text-muted-foreground" />
                        </button>
                      </TooltipTrigger>
                      <TooltipContent className="max-w-xs text-xs">
                        可填短 id（如 qwen-max）或完整 LiteLLM 串；短 id 在保存时由服务端按 provider
                        规范化。
                      </TooltipContent>
                    </Tooltip>
                  </div>
                  <Input
                    ref={modelIdInputRef}
                    className="mt-1 font-mono text-sm"
                    placeholder="gpt-4o-mini, qwen-max"
                    value={form.model_id}
                    onChange={(e) => {
                      setForm({ ...form, model_id: e.target.value })
                    }}
                  />
                </div>
              </div>

              <ModelCapabilityEditor
                values={capabilityValues}
                onChange={setCapabilityValues}
                hideUpstreamCallShape
                hideContextWindow
              />

              <div className="flex justify-end gap-2">
                <Button variant="outline" type="button" onClick={onCancel}>
                  返回模型列表
                </Button>
                <Button
                  type="button"
                  onClick={handleSubmit}
                  disabled={
                    isSubmitting ||
                    form.display_name.trim() === '' ||
                    form.model_id.trim() === '' ||
                    form.credential_id === ''
                  }
                >
                  创建
                </Button>
              </div>
            </div>
          </CollapsibleContent>
        </Collapsible>

        {!manualOpen ? (
          <div className="flex justify-start">
            <Button variant="ghost" type="button" onClick={onCancel}>
              返回模型列表
            </Button>
          </div>
        ) : null}
      </div>
    </TooltipProvider>
  )
}
