import { useMemo, useState } from 'react'

import { ChevronDown, Info } from 'lucide-react'
import { Link } from 'react-router-dom'

import type { GatewayModelCreateBody, GatewayModelPreset, ProviderCredential } from '@/api/gateway'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
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
import { CAPABILITIES, MANUAL_PRESET, NO_CREDENTIAL } from '@/features/gateway-models/constants'
import { buildPresetTags, parsePositiveInt } from '@/features/gateway-models/utils'
import { cn } from '@/lib/utils'

interface ModelFormValues {
  presetId: string
  name: string
  capability: string
  realModel: string
  credentialId: string
  provider: string
  weight: string
  rpmLimit: string
  tpmLimit: string
}

const emptyForm: ModelFormValues = {
  presetId: MANUAL_PRESET,
  name: '',
  capability: 'chat',
  realModel: '',
  credentialId: '',
  provider: 'openai',
  weight: '1',
  rpmLimit: '',
  tpmLimit: '',
}

export interface RegisterModelFormProps {
  presets: GatewayModelPreset[]
  credentials: ProviderCredential[]
  onSubmit: (body: GatewayModelCreateBody) => void
  onCancel: () => void
  isSubmitting?: boolean
  /** 嵌入凭据详情等面板：无外层 Card、紧凑页脚 */
  embedded?: boolean
  /** 锁定为当前凭据（隐藏凭据下拉） */
  lockCredentialId?: string
  lockCredentialLabel?: string
  initialProvider?: string
  cancelLabel?: string
}

function buildInitialValues(lockCredentialId?: string, initialProvider?: string): ModelFormValues {
  return {
    ...emptyForm,
    credentialId: lockCredentialId ?? '',
    provider: initialProvider ?? emptyForm.provider,
  }
}

export function RegisterModelForm({
  presets,
  credentials,
  onSubmit,
  onCancel,
  isSubmitting,
  embedded = false,
  lockCredentialId,
  lockCredentialLabel,
  initialProvider,
  cancelLabel = '返回模型清单',
}: RegisterModelFormProps): React.JSX.Element {
  const lockCredential = lockCredentialId !== undefined && lockCredentialId !== ''
  const [advancedOpen, setAdvancedOpen] = useState(false)
  const [values, setValues] = useState<ModelFormValues>(() =>
    buildInitialValues(lockCredentialId, initialProvider)
  )

  const selectedPreset = useMemo(
    () => presets.find((p) => p.id === values.presetId),
    [presets, values.presetId]
  )

  const credentialOptions = useMemo(() => {
    const matching = credentials.filter((c) => c.provider === values.provider)
    return matching.length > 0 ? matching : credentials
  }, [credentials, values.provider])

  const canSubmit =
    values.name.trim() !== '' &&
    values.realModel.trim() !== '' &&
    values.credentialId !== '' &&
    (lockCredential || credentials.length > 0)

  function handlePresetChange(presetId: string): void {
    if (presetId === MANUAL_PRESET) {
      setValues((prev) => ({ ...prev, presetId }))
      return
    }
    const preset = presets.find((item) => item.id === presetId)
    if (!preset) return
    const matchingCredential = credentials.find((c) => c.provider === preset.provider)
    setValues((prev) => ({
      ...prev,
      presetId,
      name: preset.id,
      capability: preset.capability,
      realModel: preset.real_model,
      provider: lockCredential ? prev.provider : preset.provider,
      credentialId: lockCredential
        ? prev.credentialId
        : (matchingCredential?.id ?? prev.credentialId),
    }))
  }

  function handleCredentialChange(credentialId: string): void {
    const nextId = credentialId === NO_CREDENTIAL ? '' : credentialId
    const credential = credentials.find((c) => c.id === nextId)
    setValues((prev) => ({
      ...prev,
      credentialId: nextId,
      provider: credential?.provider ?? prev.provider,
    }))
  }

  function submit(): void {
    if (!canSubmit) return
    onSubmit({
      name: values.name.trim(),
      capability: values.capability,
      real_model: values.realModel.trim(),
      credential_id: values.credentialId,
      provider: values.provider.trim(),
      weight: parsePositiveInt(values.weight) ?? 1,
      rpm_limit: parsePositiveInt(values.rpmLimit),
      tpm_limit: parsePositiveInt(values.tpmLimit),
      tags: selectedPreset ? buildPresetTags(selectedPreset) : null,
    })
  }

  return (
    <Card
      className={cn(
        embedded ? 'flex h-full min-h-0 flex-col border-0 shadow-none' : 'mx-auto w-full max-w-2xl'
      )}
    >
      {embedded ? null : (
        <CardHeader>
          <CardTitle>注册团队模型</CardTitle>
          <CardDescription>
            选择预设可快速填充；填写别名、上游模型 ID 与团队凭据后即可注册。
          </CardDescription>
        </CardHeader>
      )}
      <CardContent className={cn(embedded && 'flex-1 overflow-y-auto')}>
        <TooltipProvider delayDuration={200}>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>快速预设（可选）</Label>
              <Select value={values.presetId} onValueChange={handlePresetChange}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={MANUAL_PRESET}>手动配置</SelectItem>
                  {presets.map((preset) => (
                    <SelectItem key={preset.id} value={preset.id}>
                      {preset.name} · {preset.provider}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {selectedPreset ? (
                <div className="rounded-md border bg-muted/20 p-3 text-xs text-muted-foreground">
                  <div className="mb-2 flex flex-wrap gap-1.5">
                    {selectedPreset.recommended_for.map((tag) => (
                      <Badge key={tag} variant="secondary">
                        {tag}
                      </Badge>
                    ))}
                  </div>
                  <p>{selectedPreset.description || selectedPreset.id}</p>
                </div>
              ) : null}
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              {lockCredential ? (
                <div className="sm:col-span-2">
                  <Label>凭据</Label>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {lockCredentialLabel ?? values.credentialId}
                    <span className="ml-2 font-mono text-xs">({values.provider})</span>
                  </p>
                </div>
              ) : (
                <div className="sm:col-span-2">
                  <Label>凭据 *</Label>
                  <Select
                    value={values.credentialId || NO_CREDENTIAL}
                    onValueChange={handleCredentialChange}
                  >
                    <SelectTrigger className="mt-1">
                      <SelectValue placeholder="选择团队凭据" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value={NO_CREDENTIAL}>未选择</SelectItem>
                      {credentialOptions.map((credential) => (
                        <SelectItem key={credential.id} value={credential.id}>
                          {credential.name} · {credential.provider}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  {credentials.length === 0 ? (
                    <p className="mt-2 text-sm text-muted-foreground">
                      请先到{' '}
                      <Link to="/gateway/credentials?tab=team" className="text-primary underline">
                        凭据管理
                      </Link>{' '}
                      添加并启用团队凭据。
                    </p>
                  ) : null}
                </div>
              )}

              <div>
                <Label>提供商</Label>
                <Input
                  className="mt-1"
                  value={values.provider}
                  readOnly={lockCredential}
                  disabled={lockCredential}
                  onChange={(e) => {
                    setValues({ ...values, provider: e.target.value })
                  }}
                />
              </div>

              <div>
                <div className="mb-1 flex items-center gap-1">
                  <Label>主调用面</Label>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <button type="button" aria-label="主调用面说明">
                        <Info className="h-3.5 w-3.5 text-muted-foreground" />
                      </button>
                    </TooltipTrigger>
                    <TooltipContent className="max-w-xs text-xs">
                      与 OpenAI 兼容路由一致（chat、image、video_generation 等）。
                    </TooltipContent>
                  </Tooltip>
                </div>
                <Select
                  value={values.capability}
                  onValueChange={(v) => {
                    setValues({ ...values, capability: v })
                  }}
                >
                  <SelectTrigger className="mt-0">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {CAPABILITIES.map((capability) => (
                      <SelectItem key={capability} value={capability}>
                        {capability}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="sm:col-span-2">
                <div className="mb-1 flex items-center gap-1">
                  <Label>注册别名 *</Label>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <button type="button" aria-label="注册别名说明" className="inline-flex">
                        <Info className="h-3.5 w-3.5 text-muted-foreground" />
                      </button>
                    </TooltipTrigger>
                    <TooltipContent className="max-w-xs text-xs">
                      客户端 OpenAI 兼容请求里的 model 名称；勿与上游厂商 LiteLLM id（如
                      dashscope/qwen-max）混淆。
                    </TooltipContent>
                  </Tooltip>
                </div>
                <Input
                  className="mt-0 font-mono"
                  value={values.name}
                  onChange={(e) => {
                    setValues({ ...values, name: e.target.value })
                  }}
                  placeholder="qwen-max-prod"
                />
              </div>

              <div className="sm:col-span-2">
                <div className="mb-1 flex items-center gap-1">
                  <Label>上游模型 ID *</Label>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <button type="button" aria-label="上游模型 ID 说明" className="inline-flex">
                        <Info className="h-3.5 w-3.5 text-muted-foreground" />
                      </button>
                    </TooltipTrigger>
                    <TooltipContent className="max-w-xs text-xs">
                      可填短 id（如 qwen-max）或完整 LiteLLM 串（如 dashscope/qwen-max）；短 id
                      在保存时由服务端按所选凭据的 provider 规范化。带 / 时前缀须与 provider 一致。
                    </TooltipContent>
                  </Tooltip>
                </div>
                <Input
                  className="mt-0 font-mono"
                  value={values.realModel}
                  onChange={(e) => {
                    setValues({ ...values, realModel: e.target.value })
                  }}
                  placeholder="qwen-max"
                />
              </div>
            </div>

            <Collapsible open={advancedOpen} onOpenChange={setAdvancedOpen}>
              <CollapsibleTrigger asChild>
                <Button type="button" variant="ghost" size="sm" className="h-8 px-2 text-xs">
                  <ChevronDown
                    className={cn(
                      'mr-1 h-4 w-4 transition-transform',
                      advancedOpen && 'rotate-180'
                    )}
                  />
                  调度与限流（可选）
                </Button>
              </CollapsibleTrigger>
              <CollapsibleContent className="mt-2">
                <div className="grid gap-3 sm:grid-cols-2">
                  <div>
                    <Label>权重</Label>
                    <Input
                      className="mt-1"
                      inputMode="numeric"
                      value={values.weight}
                      onChange={(e) => {
                        setValues({ ...values, weight: e.target.value })
                      }}
                    />
                  </div>
                  <div>
                    <Label>每分钟请求</Label>
                    <Input
                      className="mt-1"
                      inputMode="numeric"
                      placeholder="不限"
                      value={values.rpmLimit}
                      onChange={(e) => {
                        setValues({ ...values, rpmLimit: e.target.value })
                      }}
                    />
                  </div>
                  <div className="sm:col-span-2 sm:max-w-[calc(50%-0.375rem)]">
                    <Label>每分钟令牌</Label>
                    <Input
                      className="mt-1"
                      inputMode="numeric"
                      placeholder="不限"
                      value={values.tpmLimit}
                      onChange={(e) => {
                        setValues({ ...values, tpmLimit: e.target.value })
                      }}
                    />
                  </div>
                </div>
              </CollapsibleContent>
            </Collapsible>
          </div>
        </TooltipProvider>
      </CardContent>
      <CardFooter className="flex shrink-0 justify-end gap-2 border-t bg-muted/20 px-4 py-3">
        <Button type="button" variant="ghost" onClick={onCancel}>
          {cancelLabel}
        </Button>
        <Button type="button" disabled={isSubmitting === true || !canSubmit} onClick={submit}>
          {isSubmitting ? '注册中…' : '注册'}
        </Button>
      </CardFooter>
    </Card>
  )
}
