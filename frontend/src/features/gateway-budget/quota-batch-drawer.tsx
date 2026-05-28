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
import { Loader2 } from '@/lib/lucide-icons'
import { OverlayScope } from '@/lib/ui-overlay'

import { BudgetModelCombobox } from './budget-model-combobox'
import { LAYER_LABELS } from './quota-rule-utils'
import {
  patchQuotaBatchFormForLayer,
  patchQuotaBatchFormForSubjectMode,
  type QuotaBatchFormValues,
} from './use-quota-center'

import type { BudgetModelOption } from './budget-model-options'

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
  metaLoading?: boolean
  modelOptions: BudgetModelOption[]
  modelsLoading?: boolean
  onModelPickerOpenChange?: (open: boolean) => void
}

function MetaListPlaceholder({
  loading,
  empty,
  emptyHint,
}: {
  loading: boolean
  empty: boolean
  emptyHint: string
}): React.JSX.Element | null {
  if (loading) {
    return (
      <p className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
        加载中…
      </p>
    )
  }
  if (empty) {
    return <p className="py-3 text-sm text-muted-foreground">{emptyHint}</p>
  }
  return null
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
  metaLoading = false,
  modelOptions,
  modelsLoading = false,
  onModelPickerOpenChange,
}: QuotaBatchDrawerProps): React.JSX.Element {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="flex max-h-[100dvh] w-full flex-col sm:max-w-lg">
        <OverlayScope className="flex min-h-0 flex-1 flex-col">
          <SheetHeader className="shrink-0 pr-8 text-left">
            <SheetTitle>批量设置配额</SheetTitle>
            <SheetDescription>
              选择层级与维度组合，统一应用限额。平台配额按全团队/成员/虚拟
              Key；上游需指定凭据；下游按虚拟 Key 写入权益套餐。
            </SheetDescription>
          </SheetHeader>

          <div className="mt-4 grid min-h-0 flex-1 gap-4 overflow-y-auto pr-1">
            <div className="space-y-2">
              <Label htmlFor="quota-batch-layer">层级</Label>
              <Select
                value={values.layer}
                onValueChange={(layer) => {
                  onChange(
                    patchQuotaBatchFormForLayer(values, layer as QuotaBatchFormValues['layer'])
                  )
                }}
                disabled={disabled}
              >
                <SelectTrigger id="quota-batch-layer">
                  <SelectValue placeholder="选择层级" />
                </SelectTrigger>
                <SelectContent>
                  {(['platform', 'upstream', 'downstream'] as const).map((layer) => (
                    <SelectItem key={layer} value={layer}>
                      {LAYER_LABELS[layer]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                {values.layer === 'platform'
                  ? '限制本团队在 Gateway 上的消费（租户/成员/Key）。'
                  : values.layer === 'upstream'
                    ? '限制上游凭据调用额度，可勾选全部凭据批量写入。'
                    : '为虚拟 Key 配置下游客户权益套餐桶。'}
              </p>
            </div>

            {values.layer === 'platform' ? (
              <>
                <div className="space-y-2">
                  <Label htmlFor="quota-batch-subject">主体</Label>
                  <Select
                    value={values.subjectMode}
                    onValueChange={(mode) => {
                      onChange(
                        patchQuotaBatchFormForSubjectMode(
                          values,
                          mode as QuotaBatchFormValues['subjectMode']
                        )
                      )
                    }}
                    disabled={disabled}
                  >
                    <SelectTrigger id="quota-batch-subject">
                      <SelectValue placeholder="选择主体" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="tenant">全团队</SelectItem>
                      <SelectItem value="users">指定成员</SelectItem>
                      <SelectItem value="keys">虚拟 Key</SelectItem>
                    </SelectContent>
                  </Select>
                  {values.subjectMode === 'tenant' ? (
                    <p className="text-xs text-muted-foreground">
                      对当前团队全体生效一条平台护栏（与成员/Key 规则可并存）。
                    </p>
                  ) : null}
                </div>
                {values.subjectMode === 'users' ? (
                  <div className="space-y-2">
                    <Label>成员（可多选）</Label>
                    <div className="max-h-40 space-y-2 overflow-y-auto rounded-md border p-2">
                      <MetaListPlaceholder
                        loading={metaLoading}
                        empty={!metaLoading && memberOptions.length === 0}
                        emptyHint="暂无成员，请先在团队页添加成员。"
                      />
                      {memberOptions.map((m) => (
                        <label
                          key={m.id}
                          className="flex cursor-pointer items-center gap-2 text-sm"
                        >
                          <Checkbox
                            checked={values.userIds.includes(m.id)}
                            disabled={disabled || metaLoading}
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
                  </div>
                ) : null}
                {values.subjectMode === 'keys' ? (
                  <div className="space-y-2">
                    <Label>虚拟 Key（可多选）</Label>
                    <div className="max-h-40 space-y-2 overflow-y-auto rounded-md border p-2">
                      <MetaListPlaceholder
                        loading={metaLoading}
                        empty={!metaLoading && keyOptions.length === 0}
                        emptyHint="暂无虚拟 Key，请先在 Key 页创建。"
                      />
                      {keyOptions.map((k) => (
                        <label
                          key={k.id}
                          className="flex cursor-pointer items-center gap-2 text-sm"
                        >
                          <Checkbox
                            checked={values.keyIds.includes(k.id)}
                            disabled={disabled || metaLoading}
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
                  </div>
                ) : null}
                <div className="space-y-2">
                  <Label htmlFor="quota-batch-period">周期</Label>
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
                    <SelectTrigger id="quota-batch-period">
                      <SelectValue placeholder="选择周期" />
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
                <label className="flex cursor-pointer items-center gap-2 text-sm">
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
                  <div className="space-y-2">
                    <Label>凭据（可多选）</Label>
                    <div className="max-h-40 space-y-2 overflow-y-auto rounded-md border p-2">
                      <MetaListPlaceholder
                        loading={metaLoading}
                        empty={!metaLoading && credentialOptions.length === 0}
                        emptyHint="暂无凭据，请先在凭据页添加。"
                      />
                      {credentialOptions.map((c) => (
                        <label
                          key={c.id}
                          className="flex cursor-pointer items-center gap-2 text-sm"
                        >
                          <Checkbox
                            checked={values.credentialIds.includes(c.id)}
                            disabled={disabled || metaLoading}
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
                  </div>
                ) : null}
                <div>
                  <Label htmlFor="quota-batch-window-up">窗口（秒，0=套餐周期）</Label>
                  <Input
                    id="quota-batch-window-up"
                    value={values.windowSeconds}
                    onChange={(e) => {
                      onChange({ ...values, windowSeconds: e.target.value })
                    }}
                    disabled={disabled}
                  />
                </div>
                <div>
                  <Label htmlFor="quota-batch-label-up">桶标签</Label>
                  <Input
                    id="quota-batch-label-up"
                    value={values.quotaLabel}
                    onChange={(e) => {
                      onChange({ ...values, quotaLabel: e.target.value })
                    }}
                    disabled={disabled}
                  />
                </div>
              </>
            ) : null}

            {values.layer === 'downstream' ? (
              <>
                <div className="space-y-2">
                  <Label>虚拟 Key（必选，可多选）</Label>
                  <div className="max-h-40 space-y-2 overflow-y-auto rounded-md border p-2">
                    <MetaListPlaceholder
                      loading={metaLoading}
                      empty={!metaLoading && keyOptions.length === 0}
                      emptyHint="暂无虚拟 Key，请先在 Key 页创建。"
                    />
                    {keyOptions.map((k) => (
                      <label key={k.id} className="flex cursor-pointer items-center gap-2 text-sm">
                        <Checkbox
                          checked={values.keyIds.includes(k.id)}
                          disabled={disabled || metaLoading}
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
                </div>
                <div>
                  <Label htmlFor="quota-batch-window-down">窗口（秒，0=套餐周期）</Label>
                  <Input
                    id="quota-batch-window-down"
                    value={values.windowSeconds}
                    onChange={(e) => {
                      onChange({ ...values, windowSeconds: e.target.value })
                    }}
                    disabled={disabled}
                  />
                </div>
                <div>
                  <Label htmlFor="quota-batch-label-down">桶标签</Label>
                  <Input
                    id="quota-batch-label-down"
                    value={values.quotaLabel}
                    onChange={(e) => {
                      onChange({ ...values, quotaLabel: e.target.value })
                    }}
                    disabled={disabled}
                  />
                </div>
              </>
            ) : null}

            <div className="space-y-2 border-t pt-4">
              <p className="text-sm font-medium">限额与模型</p>
              <label className="flex cursor-pointer items-center gap-2 text-sm">
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
                  <Label htmlFor="quota-batch-usd">限额 USD</Label>
                  <Input
                    id="quota-batch-usd"
                    value={values.limit_usd}
                    onChange={(e) => {
                      onChange({ ...values, limit_usd: e.target.value })
                    }}
                    disabled={disabled}
                    placeholder="可选"
                  />
                </div>
                <div>
                  <Label htmlFor="quota-batch-tokens">Token</Label>
                  <Input
                    id="quota-batch-tokens"
                    value={values.limit_tokens}
                    onChange={(e) => {
                      onChange({ ...values, limit_tokens: e.target.value })
                    }}
                    disabled={disabled}
                    placeholder="可选"
                  />
                </div>
                <div>
                  <Label htmlFor="quota-batch-requests">请求数</Label>
                  <Input
                    id="quota-batch-requests"
                    value={values.limit_requests}
                    onChange={(e) => {
                      onChange({ ...values, limit_requests: e.target.value })
                    }}
                    disabled={disabled}
                    placeholder="可选"
                  />
                </div>
              </div>
              <p className="text-xs text-muted-foreground">
                至少填写 USD、Token 或请求数中的一项。
              </p>
            </div>

            {values.layer === 'upstream' && values.allCredentials ? (
              <p className="text-xs text-amber-600">
                将为本团队每个凭据各创建/更新一条上游配额（无 active plan 时会自动创建 plan 头）。
              </p>
            ) : null}
          </div>

          <SheetFooter className="mt-4 shrink-0 flex-row items-center justify-between gap-2 border-t pt-4 sm:justify-between">
            <p className="text-sm text-muted-foreground">
              预览：将写入 {String(previewCount)} 条
              {previewCount === 0 ? '（请完善主体与限额）' : ''}
            </p>
            <div className="flex gap-2">
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
            </div>
          </SheetFooter>
        </OverlayScope>
      </SheetContent>
    </Sheet>
  )
}
