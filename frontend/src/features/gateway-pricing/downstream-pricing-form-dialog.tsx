import { useEffect, useState } from 'react'
import type React from 'react'

import type { DownstreamPricingRow, DownstreamPricingUpsertBody } from '@/api/gateway'
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
import { Loader2 } from '@/lib/lucide-icons'
import type { DisplayCurrency } from '@/types/money'

import {
  buildDownstreamPricingPayload,
  type DownstreamPricingFormValues,
} from './pricing-form-payloads'

function initialValues(row: DownstreamPricingRow | null): DownstreamPricingFormValues {
  return {
    gateway_model_id: row?.gateway_model_id ?? '',
    inheritance_strategy: row?.inheritance_strategy === 'mirror' ? 'mirror' : 'manual',
    input: row?.input_cost_per_million_display?.amount ?? '',
    output: row?.output_cost_per_million_display?.amount ?? '',
    cache_creation: '',
    cache_read: '',
    per_request: '',
  }
}

export function DownstreamPricingFormDialog({
  open,
  onOpenChange,
  row,
  currency,
  submitting,
  onSubmit,
}: Readonly<{
  open: boolean
  onOpenChange: (open: boolean) => void
  row: DownstreamPricingRow | null
  currency: DisplayCurrency
  submitting?: boolean
  onSubmit: (body: DownstreamPricingUpsertBody) => void
}>): React.JSX.Element {
  const [values, setValues] = useState<DownstreamPricingFormValues>(() => initialValues(row))

  useEffect(() => {
    if (!open) return
    setValues(initialValues(row))
  }, [open, row])

  const isManual = values.inheritance_strategy === 'manual'
  const canSubmit =
    !submitting &&
    (!isManual || (Number.isFinite(Number(values.input)) && Number.isFinite(Number(values.output))))

  const update = (key: keyof DownstreamPricingFormValues, value: string): void => {
    setValues((current) => ({ ...current, [key]: value }))
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>调整下游售价</DialogTitle>
        </DialogHeader>
        <div className="grid gap-3 py-2">
          <div className="space-y-2">
            <Label>模型 ID</Label>
            <Input
              value={values.gateway_model_id}
              disabled={Boolean(row?.gateway_model_id)}
              onChange={(event) => {
                update('gateway_model_id', event.target.value)
              }}
              placeholder="留空仅用于 scope 默认价；模型调价需填写模型 ID"
            />
          </div>

          <div className="space-y-2">
            <Label>策略</Label>
            <Select
              value={values.inheritance_strategy}
              onValueChange={(value) => {
                update('inheritance_strategy', value as 'mirror' | 'manual')
              }}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="mirror">跟随上游</SelectItem>
                <SelectItem value="manual">自定义售价</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {isManual ? (
            <>
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label>输入价 / 1M tokens ({currency})</Label>
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
                  <Label>输出价 / 1M tokens ({currency})</Label>
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

              <div className="space-y-2">
                <Label>固定请求费（可选，{currency}）</Label>
                <Input
                  type="number"
                  min="0"
                  step="0.0001"
                  value={values.per_request}
                  onChange={(event) => {
                    update('per_request', event.target.value)
                  }}
                />
              </div>
            </>
          ) : (
            <p className="rounded-md bg-muted/40 p-3 text-sm text-muted-foreground">
              保存后该模型售价会重新跟随上游成本，当前自定义价格会被关闭为历史版本。
            </p>
          )}

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
              if (canSubmit) onSubmit(buildDownstreamPricingPayload(values, currency))
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
