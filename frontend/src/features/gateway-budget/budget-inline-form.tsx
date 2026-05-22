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

import type { BudgetAdminTab } from './budget-admin-constants'
import type { BudgetFormValues } from './budget-form-utils'

export interface BudgetInlineFormProps {
  values: BudgetFormValues
  onChange: (next: BudgetFormValues) => void
  onSubmit: () => void
  onCancel?: () => void
  submitLabel: string
  disabled: boolean
  keys: { id: string; label: string }[]
  members: { id: string; label: string }[]
  modelOptions: string[]
  fixedTargetKind?: BudgetAdminTab
}

export function BudgetInlineForm({
  values,
  onChange,
  onSubmit,
  onCancel,
  submitLabel,
  disabled,
  keys,
  members,
  modelOptions,
  fixedTargetKind,
}: Readonly<BudgetInlineFormProps>): React.JSX.Element {
  const targetKind = fixedTargetKind ?? values.target_kind

  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {!fixedTargetKind ? (
        <div>
          <Label>作用域</Label>
          <Select
            value={values.target_kind}
            onValueChange={(val: string) => {
              onChange({
                ...values,
                target_kind: val as BudgetFormValues['target_kind'],
                target_id: '',
              })
            }}
            disabled={disabled}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="tenant">团队</SelectItem>
              <SelectItem value="user">用户</SelectItem>
              <SelectItem value="key">虚拟 Key</SelectItem>
              <SelectItem value="system">系统</SelectItem>
            </SelectContent>
          </Select>
        </div>
      ) : null}
      {targetKind === 'user' ? (
        <div className={fixedTargetKind ? 'sm:col-span-2' : undefined}>
          <Label>用户</Label>
          <Select
            value={values.target_id || undefined}
            onValueChange={(val: string) => {
              onChange({ ...values, target_id: val })
            }}
            disabled={disabled}
          >
            <SelectTrigger>
              <SelectValue placeholder="选择团队成员" />
            </SelectTrigger>
            <SelectContent>
              {members.map((m) => (
                <SelectItem key={m.id} value={m.id}>
                  {m.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      ) : null}
      {targetKind === 'key' ? (
        <div className={fixedTargetKind ? 'sm:col-span-2' : undefined}>
          <Label>虚拟 Key</Label>
          <Select
            value={values.target_id || undefined}
            onValueChange={(val: string) => {
              onChange({ ...values, target_id: val })
            }}
            disabled={disabled}
          >
            <SelectTrigger>
              <SelectValue placeholder="选择虚拟 Key" />
            </SelectTrigger>
            <SelectContent>
              {keys.map((k) => (
                <SelectItem key={k.id} value={k.id}>
                  {k.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      ) : null}
      <div>
        <Label>周期</Label>
        <Select
          value={values.period}
          onValueChange={(val: string) => {
            onChange({ ...values, period: val as BudgetFormValues['period'] })
          }}
          disabled={disabled}
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="daily">每日</SelectItem>
            <SelectItem value="monthly">每月</SelectItem>
            <SelectItem value="total">总额（不限期滚动）</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className="sm:col-span-2">
        <Label>模型（可选）</Label>
        {modelOptions.length > 0 ? (
          <Select
            value={values.model_name || '__all__'}
            onValueChange={(val: string) => {
              onChange({ ...values, model_name: val === '__all__' ? '' : val })
            }}
            disabled={disabled}
          >
            <SelectTrigger>
              <SelectValue placeholder="全模型汇总" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__all__">全模型汇总</SelectItem>
              {modelOptions.map((name) => (
                <SelectItem key={name} value={name}>
                  {name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        ) : (
          <Input
            placeholder="与 API 请求中 model 一致；留空表示全模型汇总"
            value={values.model_name}
            onChange={(e) => {
              onChange({ ...values, model_name: e.target.value })
            }}
            disabled={disabled}
          />
        )}
      </div>
      <div>
        <Label>限额 USD（可选）</Label>
        <Input
          type="text"
          inputMode="decimal"
          value={values.limit_usd}
          onChange={(e) => {
            onChange({ ...values, limit_usd: e.target.value })
          }}
          disabled={disabled}
        />
      </div>
      <div>
        <Label>软限额 USD（可选）</Label>
        <Input
          type="text"
          inputMode="decimal"
          value={values.soft_limit_usd}
          onChange={(e) => {
            onChange({ ...values, soft_limit_usd: e.target.value })
          }}
          disabled={disabled}
        />
      </div>
      <div>
        <Label>限额 Token（可选）</Label>
        <Input
          type="text"
          inputMode="numeric"
          value={values.limit_tokens}
          onChange={(e) => {
            onChange({ ...values, limit_tokens: e.target.value })
          }}
          disabled={disabled}
        />
      </div>
      <div>
        <Label>限额请求数（可选）</Label>
        <Input
          type="text"
          inputMode="numeric"
          value={values.limit_requests}
          onChange={(e) => {
            onChange({ ...values, limit_requests: e.target.value })
          }}
          disabled={disabled}
        />
      </div>
      <div className="flex flex-wrap gap-2 sm:col-span-2">
        <Button type="button" onClick={onSubmit} disabled={disabled}>
          {submitLabel}
        </Button>
        {onCancel ? (
          <Button type="button" variant="ghost" onClick={onCancel} disabled={disabled}>
            取消
          </Button>
        ) : null}
      </div>
    </div>
  )
}
