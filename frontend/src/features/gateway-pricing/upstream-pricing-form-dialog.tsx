import { useEffect, useState } from 'react'
import type React from 'react'

import type {
  EffectiveProvider,
  UpstreamPricingRow,
  UpstreamPricingUpsertBody,
} from '@/api/gateway/pricing'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
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
import { providerLabel } from '@/features/gateway-credentials/provider-schemas'
import { Loader2 } from '@/lib/lucide-icons'

import {
  buildUpstreamPricingPayload,
  type UpstreamPricingFormValues,
} from './pricing-form-payloads'
import { UPSTREAM_DISPLAY_CURRENCY } from './upstream-pricing-view'

function initialValues(
  row: UpstreamPricingRow | null,
  providers: readonly EffectiveProvider[]
): UpstreamPricingFormValues {
  return {
    provider: row?.provider ?? (providers.length > 0 ? providers[0].provider : ''),
    upstream_model: row?.upstream_model ?? '',
    capability: row?.capability ?? 'chat',
    input: row?.input_cost_per_million_display?.amount ?? '',
    output: row?.output_cost_per_million_display?.amount ?? '',
    cache_creation: '',
    cache_read: '',
  }
}

export function UpstreamPricingFormDialog({
  open,
  onOpenChange,
  row,
  providers,
  submitting,
  onSubmit,
}: Readonly<{
  open: boolean
  onOpenChange: (open: boolean) => void
  row: UpstreamPricingRow | null
  providers: readonly EffectiveProvider[]
  submitting?: boolean
  onSubmit: (body: UpstreamPricingUpsertBody) => void
}>): React.JSX.Element {
  const [values, setValues] = useState<UpstreamPricingFormValues>(() =>
    initialValues(row, providers)
  )

  useEffect(() => {
    if (!open) return
    setValues(initialValues(row, providers))
  }, [open, row, providers])

  const providerAllowed = providers.some((p) => p.provider === values.provider)
  const canSubmit =
    !submitting &&
    providerAllowed &&
    Boolean(values.upstream_model.trim()) &&
    Boolean(values.capability.trim()) &&
    Number.isFinite(Number(values.input)) &&
    Number.isFinite(Number(values.output))

  const update = (key: keyof UpstreamPricingFormValues, value: string): void => {
    setValues((current) => ({ ...current, [key]: value }))
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{row ? '调整上游成本' : '新增上游成本'}</DialogTitle>
          <DialogDescription>
            {row
              ? '更新该提供商模型的输入/输出单价。'
              : '为已接入提供商登记上游模型的 token 成本。'}
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-3 py-2">
          <div className="space-y-2">
            <Label>提供商</Label>
            <Select
              value={values.provider}
              disabled={Boolean(row)}
              onValueChange={(provider) => {
                update('provider', provider)
              }}
            >
              <SelectTrigger>
                <SelectValue placeholder="请选择已接入提供商" />
              </SelectTrigger>
              <SelectContent>
                {providers.map((provider) => (
                  <SelectItem key={provider.provider} value={provider.provider}>
                    {providerLabel(provider.provider)} ({provider.credential_count})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {!providerAllowed ? (
              <p className="text-[11px] text-destructive">只能维护已配置凭据的提供商。</p>
            ) : null}
          </div>

          <div className="space-y-2">
            <Label>上游模型</Label>
            <Input
              value={values.upstream_model}
              disabled={Boolean(row)}
              onChange={(event) => {
                update('upstream_model', event.target.value)
              }}
              placeholder="openai/gpt-4o-mini"
            />
          </div>

          <div className="space-y-2">
            <Label>能力</Label>
            <Input
              value={values.capability}
              disabled={Boolean(row)}
              onChange={(event) => {
                update('capability', event.target.value)
              }}
              placeholder="chat"
            />
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>输入价 / 1M tokens (USD)</Label>
              <Input
                type="number"
                min="0"
                step="0.0001"
                value={values.input}
                onChange={(event) => {
                  update('input', event.target.value)
                }}
              />
            </div>
            <div className="space-y-2">
              <Label>输出价 / 1M tokens (USD)</Label>
              <Input
                type="number"
                min="0"
                step="0.0001"
                value={values.output}
                onChange={(event) => {
                  update('output', event.target.value)
                }}
              />
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>缓存写入 / 1M（可选）</Label>
              <Input
                type="number"
                min="0"
                step="0.0001"
                value={values.cache_creation}
                onChange={(event) => {
                  update('cache_creation', event.target.value)
                }}
              />
            </div>
            <div className="space-y-2">
              <Label>缓存读取 / 1M（可选）</Label>
              <Input
                type="number"
                min="0"
                step="0.0001"
                value={values.cache_read}
                onChange={(event) => {
                  update('cache_read', event.target.value)
                }}
              />
            </div>
          </div>
          <p className="text-[11px] text-muted-foreground">
            保存会创建新版本并关闭当前生效版本，不会覆盖历史价格。
          </p>
        </div>
        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => {
              onOpenChange(false)
            }}
          >
            取消
          </Button>
          <Button
            type="button"
            disabled={!canSubmit}
            onClick={() => {
              if (canSubmit)
                onSubmit(buildUpstreamPricingPayload(values, UPSTREAM_DISPLAY_CURRENCY))
            }}
          >
            {submitting ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" /> : null}
            保存
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
