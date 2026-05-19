import { useCallback, useMemo, useState } from 'react'

import type { PersonalGatewayModel } from '@/api/gateway'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
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
import { CredentialUpstreamModelsPanel } from '@/features/gateway-credentials/credential-upstream-models-panel'
import { NO_CREDENTIAL } from '@/features/gateway-models/constants'
import { Loader2, Info, ChevronDown } from '@/lib/lucide-icons'
import type { ModelType } from '@/types/user-model'
import { MODEL_PROVIDERS, MODEL_TYPE_LABELS } from '@/types/user-model'

import { personalModelFormValuesFromModel } from './personal-model-form-values'

export interface PersonalModelFormValues {
  display_name: string
  provider: string
  model_id: string
  credential_id: string
  model_types: ModelType[]
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
}

export function PersonalModelForm({
  mode,
  credentials,
  initial = null,
  onSubmit,
  onCancel,
  isSubmitting,
}: PersonalModelFormProps): React.JSX.Element {
  const activeCredentials = useMemo(() => credentials.filter((c) => c.is_active), [credentials])
  const [form, setForm] = useState<PersonalModelFormValues>(() =>
    initial ? personalModelFormValuesFromModel(initial) : { ...EMPTY_FORM }
  )

  const credentialOptions = useMemo(() => {
    const matching = activeCredentials.filter((c) => c.provider === form.provider)
    return matching.length > 0 ? matching : activeCredentials
  }, [activeCredentials, form.provider])

  const handlePickUpstreamModelId = useCallback((upstreamId: string): void => {
    setForm((prev) => ({ ...prev, model_id: upstreamId }))
  }, [])

  function toggleType(t: ModelType): void {
    if (mode === 'edit') return
    const current = form.model_types
    const next = current.includes(t) ? current.filter((x) => x !== t) : [...current, t]
    if (next.length === 0) return
    setForm({ ...form, model_types: next })
  }

  function handleSubmit(): void {
    onSubmit(form)
  }

  const title =
    mode === 'create' ? '\u6dfb\u52a0\u4e2a\u4eba\u6a21\u578b' : '\u7f16\u8f91\u6a21\u578b'
  const descCreate =
    '\u9009\u62e9\u5df2\u914d\u7f6e\u7684\u4e2a\u4eba\u51ed\u636e\u5e76\u6ce8\u518c\u6a21\u578b'
  const descEdit =
    '\u4fee\u6539\u6a21\u578b\u914d\u7f6e\uff08\u591a\u80fd\u529b\u62c6\u5206\u4e3a\u591a\u884c\u65f6\u4ec5\u7f16\u8f91\u5f53\u524d\u884c\uff09'

  return (
    <TooltipProvider delayDuration={0}>
      <div className="mx-auto max-w-lg space-y-4 rounded-lg border bg-card p-6">
        <div>
          <h3 className="text-lg font-semibold">{title}</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            {mode === 'create' ? descCreate : descEdit}
          </p>
        </div>

        <div className="grid gap-4">
          <div className="grid gap-1.5">
            <Label>{'\u540d\u79f0'} *</Label>
            <Input
              placeholder={'\u5982\uff1a\u6211\u7684 GPT-4o'}
              value={form.display_name}
              onChange={(e) => {
                setForm({ ...form, display_name: e.target.value })
              }}
            />
          </div>

          <div className="grid gap-1.5">
            <Label>{'\u63d0\u4f9b\u5546'} *</Label>
            <Select
              value={form.provider}
              disabled={mode === 'edit'}
              onValueChange={(v) => {
                setForm({ ...form, provider: v, credential_id: '' })
              }}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {MODEL_PROVIDERS.map((p) => (
                  <SelectItem key={p.id} value={p.id}>
                    {p.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="grid gap-1.5">
            <div className="flex items-center gap-1">
              <Label>{'\u6a21\u578b ID'} *</Label>
              <Tooltip>
                <TooltipTrigger asChild>
                  <button
                    type="button"
                    aria-label={'\u6a21\u578b ID \u8bf4\u660e'}
                    className="inline-flex"
                  >
                    <Info className="h-3.5 w-3.5 text-muted-foreground" />
                  </button>
                </TooltipTrigger>
                <TooltipContent className="max-w-xs text-xs">
                  {
                    '\u53ef\u586b\u77ed id\uff08\u5982 qwen-max\uff09\u6216\u5e26\u5382\u5546\u524d\u7f00\u7684 LiteLLM \u4e32\uff1b\u670d\u52a1\u7aef\u4f1a\u6309\u6240\u9009 provider \u89c4\u8303\u5316\u540e\u518d\u5199\u5165\u3002'
                  }
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
            <Label>{'\u51ed\u636e'} *</Label>
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
                <SelectItem value={NO_CREDENTIAL}>{'\u672a\u9009\u62e9'}</SelectItem>
                {credentialOptions.map((c) => (
                  <SelectItem key={c.id} value={c.id}>
                    {c.name}
                    {'\u00b7'}
                    {c.provider}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {mode === 'create' && form.credential_id ? (
            <Collapsible className="rounded-md border">
              <CollapsibleTrigger asChild>
                <Button
                  variant="outline"
                  type="button"
                  className="flex w-full items-center justify-between"
                >
                  <span>?????????</span>
                  <ChevronDown className="h-4 w-4 shrink-0 opacity-60" />
                </Button>
              </CollapsibleTrigger>
              <CollapsibleContent className="border-t p-2">
                <CredentialUpstreamModelsPanel
                  scope="user"
                  credentialId={form.credential_id}
                  provider={form.provider}
                  onPickModelId={handlePickUpstreamModelId}
                />
              </CollapsibleContent>
            </Collapsible>
          ) : null}

          {mode === 'create' ? (
            <div className="grid gap-1.5">
              <Label>{'\u6a21\u578b\u7c7b\u578b'}</Label>
              <div className="flex flex-wrap gap-4">
                {(['text', 'image', 'image_gen', 'video'] as ModelType[]).map((t) => (
                  <label key={t} className="flex cursor-pointer items-center gap-1.5 text-sm">
                    <Checkbox
                      checked={form.model_types.includes(t)}
                      onCheckedChange={() => {
                        toggleType(t)
                      }}
                    />
                    {MODEL_TYPE_LABELS[t]}
                  </label>
                ))}
              </div>
            </div>
          ) : null}
        </div>

        <div className="flex justify-end gap-2">
          <Button variant="outline" type="button" onClick={onCancel}>
            {'\u53d6\u6d88'}
          </Button>
          <Button type="button" onClick={handleSubmit} disabled={isSubmitting}>
            {isSubmitting ? <Loader2 className="mr-1 h-4 w-4 animate-spin" /> : null}
            {mode === 'create' ? '\u521b\u5efa' : '\u4fdd\u5b58'}
          </Button>
        </div>
      </div>
    </TooltipProvider>
  )
}
