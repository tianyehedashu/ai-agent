import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'

import { BudgetModelCombobox } from './budget-model-combobox'
import { LAYER_LABELS } from './quota-rule-utils'

import type { BudgetModelOption } from './budget-model-options'
import type { QuotaBatchFormValues } from './use-quota-center'

export interface QuotaBatchDrawerProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  values: QuotaBatchFormValues
  onChange: (values: QuotaBatchFormValues) => void
  onSubmit: () => void
  disabled: boolean
  pending: boolean
  previewCount: number
  memberOptions: { id: string; label: string }[]
  keyOptions: { id: string; label: string }[]
  credentialOptions: { id: string; label: string }[]
  modelOptions: BudgetModelOption[]
  modelsLoading?: boolean
  onModelPickerOpenChange?: (open: boolean) => void
}

export function QuotaBatchDrawer({
  open,
  onOpenChange,
  values,
  onChange,
  onSubmit,
  disabled,
  pending,
  previewCount,
  memberOptions,
  keyOptions,
  credentialOptions,
  modelOptions,
  modelsLoading = false,
  onModelPickerOpenChange,
}: QuotaBatchDrawerProps): React.JSX.Element {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="overflow-y-auto sm:max-w-lg">
        <SheetHeader>
          <SheetTitle>批量设置配额</SheetTitle>
          <SheetDescription>
            选择层级与维度组合，统一应用限额。平台配额按团队/成员/Key；上游配额需指定凭据。
          </SheetDescription>
        </SheetHeader>

        <div className="mt-4 grid gap-4">
          <div>
            <Label>层级</Label>
            <Select
              value={values.layer}
              onValueChange={(layer) => {
                onChange({ ...values, layer: layer as QuotaBatchFormValues['layer'] })
              }}
              disabled={disabled}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {(['platform', 'upstream', 'downstream'] as const).map((layer) => (
                  <SelectItem key={layer} value={layer}>
                    {LAYER_LABELS[layer]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {values.layer === 'platform' ? (
            <>
              <div>
                <Label>主体</Label>
                <Select
                  value={values.subjectMode}
                  onValueChange={(mode) => {
                    onChange({
                      ...values,
                      subjectMode: mode as QuotaBatchFormValues['subjectMode'],
                    })
                  }}
                  disabled={disabled}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="tenant">全团队</SelectItem>
                    <SelectItem value="users">指定成员</SelectItem>
                    <SelectItem value="keys">虚拟 Key</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              {values.subjectMode === 'users' ? (
                <div className="max-h-40 space-y-2 overflow-y-auto rounded border p-2">
                  {memberOptions.map((m) => (
                    <label key={m.id} className="flex items-center gap-2 text-sm">
                      <Checkbox
                        checked={values.userIds.includes(m.id)}
                        disabled={disabled}
                        onCheckedChange={(checked) => {
                          const next = checked
                            ? [...values.userIds, m.id]
                            : values.userIds.filter((id) => id !== m.id)
                          onChange({ ...values, userIds: next })
                        }}
                      />
                      {m.label}
                    </label>
                  ))}
                </div>
              ) : null}
              {values.subjectMode === 'keys' ? (
                <div className="max-h-40 space-y-2 overflow-y-auto rounded border p-2">
                  {keyOptions.map((k) => (
                    <label key={k.id} className="flex items-center gap-2 text-sm">
                      <Checkbox
                        checked={values.keyIds.includes(k.id)}
                        disabled={disabled}
                        onCheckedChange={(checked) => {
                          const next = checked
                            ? [...values.keyIds, k.id]
                            : values.keyIds.filter((id) => id !== k.id)
                          onChange({ ...values, keyIds: next })
                        }}
                      />
                      {k.label}
                    </label>
                  ))}
                </div>
              ) : null}
              <div>
                <Label>周期</Label>
                <Select
                  value={values.period}
                  onValueChange={(period) => {
                    onChange({
                      ...values,
                      period: period as QuotaBatchFormValues['period'],
                    })
                  }}
                  disabled={disabled}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="daily">每日</SelectItem>
                    <SelectItem value="monthly">每月</SelectItem>
                    <SelectItem value="total">总额</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </>
          ) : null}

          {values.layer === 'upstream' ? (
            <>
              <label className="flex items-center gap-2 text-sm">
                <Checkbox
                  checked={values.allCredentials}
                  disabled={disabled}
                  onCheckedChange={(checked) => {
                    onChange({ ...values, allCredentials: checked === true })
                  }}
                />
                全部凭据
              </label>
              {!values.allCredentials ? (
                <div className="max-h-40 space-y-2 overflow-y-auto rounded border p-2">
                  {credentialOptions.map((c) => (
                    <label key={c.id} className="flex items-center gap-2 text-sm">
                      <Checkbox
                        checked={values.credentialIds.includes(c.id)}
                        disabled={disabled}
                        onCheckedChange={(checked) => {
                          const next = checked
                            ? [...values.credentialIds, c.id]
                            : values.credentialIds.filter((id) => id !== c.id)
                          onChange({ ...values, credentialIds: next })
                        }}
                      />
                      {c.label}
                    </label>
                  ))}
                </div>
              ) : null}
              <div>
                <Label>窗口（秒，0=套餐周期）</Label>
                <Input
                  value={values.windowSeconds}
                  onChange={(e) => {
                    onChange({ ...values, windowSeconds: e.target.value })
                  }}
                  disabled={disabled}
                />
              </div>
              <div>
                <Label>桶标签</Label>
                <Input
                  value={values.quotaLabel}
                  onChange={(e) => {
                    onChange({ ...values, quotaLabel: e.target.value })
                  }}
                  disabled={disabled}
                />
              </div>
            </>
          ) : null}

          <label className="flex items-center gap-2 text-sm">
            <Checkbox
              checked={values.allModels}
              disabled={disabled}
              onCheckedChange={(checked) => {
                onChange({ ...values, allModels: checked === true })
              }}
            />
            全模型汇总
          </label>
          {!values.allModels ? (
            <div>
              <Label>模型（可多选，逐条添加）</Label>
              <BudgetModelCombobox
                value=""
                onChange={(name) => {
                  if (name && !values.modelNames.includes(name)) {
                    onChange({ ...values, modelNames: [...values.modelNames, name] })
                  }
                }}
                options={modelOptions}
                loading={modelsLoading}
                placeholder="选择模型…"
                onPopoverOpenChange={onModelPickerOpenChange}
              />
              {values.modelNames.length > 0 ? (
                <div className="mt-2 flex flex-wrap gap-1">
                  {values.modelNames.map((name) => (
                    <Button
                      key={name}
                      type="button"
                      size="sm"
                      variant="secondary"
                      className="h-7 text-xs"
                      disabled={disabled}
                      onClick={() => {
                        onChange({
                          ...values,
                          modelNames: values.modelNames.filter((n) => n !== name),
                        })
                      }}
                    >
                      {name} ×
                    </Button>
                  ))}
                </div>
              ) : null}
            </div>
          ) : null}

          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>限额 USD</Label>
              <Input
                value={values.limit_usd}
                onChange={(e) => {
                  onChange({ ...values, limit_usd: e.target.value })
                }}
                disabled={disabled}
              />
            </div>
            {values.layer === 'platform' ? (
              <div>
                <Label>软限额 USD</Label>
                <Input
                  value={values.soft_limit_usd}
                  onChange={(e) => {
                    onChange({ ...values, soft_limit_usd: e.target.value })
                  }}
                  disabled={disabled}
                />
              </div>
            ) : null}
            <div>
              <Label>Token</Label>
              <Input
                value={values.limit_tokens}
                onChange={(e) => {
                  onChange({ ...values, limit_tokens: e.target.value })
                }}
                disabled={disabled}
              />
            </div>
            <div>
              <Label>请求数</Label>
              <Input
                value={values.limit_requests}
                onChange={(e) => {
                  onChange({ ...values, limit_requests: e.target.value })
                }}
                disabled={disabled}
              />
            </div>
          </div>

          {values.layer === 'upstream' && values.allCredentials ? (
            <p className="text-xs text-amber-600">
              将为本团队每个凭据各创建/更新一条上游配额（无 active plan 时会自动创建 plan 头）。
            </p>
          ) : null}
        </div>

        <SheetFooter className="mt-6">
          <p className="mr-auto text-sm text-muted-foreground">
            预览：将写入 {String(previewCount)} 条
          </p>
          <Button
            variant="outline"
            onClick={() => {
              onOpenChange(false)
            }}
            disabled={pending}
          >
            取消
          </Button>
          <Button onClick={onSubmit} disabled={disabled || pending || previewCount === 0}>
            {pending ? '保存中…' : '确认保存'}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}
