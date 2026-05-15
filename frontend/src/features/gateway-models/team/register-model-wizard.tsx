import { useMemo, useState } from 'react'

import { Info } from 'lucide-react'
import { Link } from 'react-router-dom'

import type { GatewayModelCreateBody, GatewayModelPreset, ProviderCredential } from '@/api/gateway'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
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

const STEPS = ['来源', '通道与凭据', '别名与上游', '调度', '确认'] as const

interface RegisterModelWizardProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  presets: GatewayModelPreset[]
  credentials: ProviderCredential[]
  onSubmit: (body: GatewayModelCreateBody) => void
  isSubmitting?: boolean
}

export function RegisterModelWizard({
  open,
  onOpenChange,
  presets,
  credentials,
  onSubmit,
  isSubmitting,
}: RegisterModelWizardProps): React.JSX.Element {
  const [step, setStep] = useState(0)
  const [values, setValues] = useState<ModelFormValues>(emptyForm)

  const selectedPreset = useMemo(
    () => presets.find((p) => p.id === values.presetId),
    [presets, values.presetId]
  )

  const credentialOptions = useMemo(() => {
    const matching = credentials.filter((c) => c.provider === values.provider)
    return matching.length > 0 ? matching : credentials
  }, [credentials, values.provider])

  function resetAndClose(nextOpen: boolean): void {
    if (!nextOpen) {
      setStep(0)
      setValues(emptyForm)
    }
    onOpenChange(nextOpen)
  }

  function handlePresetChange(presetId: string): void {
    if (presetId === MANUAL_PRESET) {
      setValues({ ...values, presetId })
      return
    }
    const preset = presets.find((item) => item.id === presetId)
    if (!preset) return
    const matchingCredential = credentials.find((c) => c.provider === preset.provider)
    setValues({
      ...values,
      presetId,
      name: preset.id,
      capability: preset.capability,
      realModel: preset.real_model,
      provider: preset.provider,
      credentialId: matchingCredential?.id ?? values.credentialId,
    })
  }

  function submit(): void {
    if (!values.name.trim() || !values.realModel.trim() || !values.credentialId) return
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

  const canNext =
    step === 0 ||
    (step === 1 && values.credentialId.length > 0 && credentials.length > 0) ||
    (step === 2 && values.name.trim() && values.realModel.trim()) ||
    step === 3

  return (
    <Dialog open={open} onOpenChange={resetAndClose}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>注册模型</DialogTitle>
          <p className="text-sm text-muted-foreground">
            步骤 {step + 1}/{STEPS.length}：{STEPS[step]}
          </p>
        </DialogHeader>
        <TooltipProvider delayDuration={200}>
          <div className="min-h-[240px] py-2">
            {step === 0 && (
              <div className="space-y-3">
                <Label>常用预设</Label>
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
            )}

            {step === 1 && (
              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <Label>提供商</Label>
                  <Input
                    value={values.provider}
                    onChange={(e) => {
                      setValues({ ...values, provider: e.target.value })
                    }}
                  />
                </div>
                <div className="sm:col-span-2">
                  <Label>凭据</Label>
                  <Select
                    value={values.credentialId || NO_CREDENTIAL}
                    onValueChange={(v) => {
                      setValues({ ...values, credentialId: v === NO_CREDENTIAL ? '' : v })
                    }}
                  >
                    <SelectTrigger>
                      <SelectValue />
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
              </div>
            )}

            {step === 2 && (
              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <Label>注册别名</Label>
                  <Input
                    value={values.name}
                    onChange={(e) => {
                      setValues({ ...values, name: e.target.value })
                    }}
                    placeholder="dashscope/qwen-max"
                    className="font-mono"
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
                    <SelectTrigger>
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
                  <Label>上游模型 ID</Label>
                  <Input
                    value={values.realModel}
                    onChange={(e) => {
                      setValues({ ...values, realModel: e.target.value })
                    }}
                    className="font-mono"
                  />
                </div>
              </div>
            )}

            {step === 3 && (
              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <Label>权重</Label>
                  <Input
                    inputMode="numeric"
                    value={values.weight}
                    onChange={(e) => {
                      setValues({ ...values, weight: e.target.value })
                    }}
                  />
                </div>
                <div className="grid grid-cols-2 gap-2 sm:col-span-2">
                  <div>
                    <Label>每分钟请求</Label>
                    <Input
                      inputMode="numeric"
                      placeholder="不限"
                      value={values.rpmLimit}
                      onChange={(e) => {
                        setValues({ ...values, rpmLimit: e.target.value })
                      }}
                    />
                  </div>
                  <div>
                    <Label>每分钟令牌</Label>
                    <Input
                      inputMode="numeric"
                      placeholder="不限"
                      value={values.tpmLimit}
                      onChange={(e) => {
                        setValues({ ...values, tpmLimit: e.target.value })
                      }}
                    />
                  </div>
                </div>
              </div>
            )}

            {step === 4 && (
              <dl className="space-y-2 text-sm">
                <div className="flex justify-between gap-4">
                  <dt className="text-muted-foreground">别名</dt>
                  <dd className="font-mono">{values.name}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-muted-foreground">上游</dt>
                  <dd className="text-right font-mono">{values.realModel}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-muted-foreground">调用面</dt>
                  <dd>{values.capability}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-muted-foreground">权重 / 限流</dt>
                  <dd className="text-right tabular-nums">
                    {values.weight} · RPM {values.rpmLimit || '∞'} · TPM {values.tpmLimit || '∞'}
                  </dd>
                </div>
              </dl>
            )}
          </div>
          <DialogFooter className="gap-2 sm:justify-between">
            <Button
              type="button"
              variant="ghost"
              disabled={step === 0}
              onClick={() => {
                setStep((s) => Math.max(0, s - 1))
              }}
            >
              上一步
            </Button>
            <div className="flex gap-2">
              <Button
                type="button"
                variant="ghost"
                onClick={() => {
                  resetAndClose(false)
                }}
              >
                取消
              </Button>
              {step < STEPS.length - 1 ? (
                <Button
                  type="button"
                  disabled={!canNext}
                  onClick={() => {
                    setStep((s) => s + 1)
                  }}
                >
                  下一步
                </Button>
              ) : (
                <Button
                  type="button"
                  disabled={
                    isSubmitting === true ||
                    values.name.trim() === '' ||
                    values.realModel.trim() === '' ||
                    values.credentialId === ''
                  }
                  onClick={submit}
                >
                  {isSubmitting ? '注册中…' : '注册'}
                </Button>
              )}
            </div>
          </DialogFooter>
        </TooltipProvider>
      </DialogContent>
    </Dialog>
  )
}
