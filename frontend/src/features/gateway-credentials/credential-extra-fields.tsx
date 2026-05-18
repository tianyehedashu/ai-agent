/**
 * 凭据 extra 字段动态渲染器（按 provider schema 驱动）。
 * 在新增弹窗与个人编辑弹窗中共用，保持单一渲染规则。
 * 工具函数请见 [`credential-extra-utils.ts`](./credential-extra-utils.ts)。
 */

import type React from 'react'

import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'

import type { CredentialExtraValues } from './credential-extra-utils'
import type { CredentialFieldSpec } from './provider-schemas'

export function ExtraFieldsRenderer({
  fields,
  values,
  onChange,
  idPrefix = 'cred-extra',
}: Readonly<{
  fields: ReadonlyArray<CredentialFieldSpec>
  values: CredentialExtraValues
  onChange: (next: CredentialExtraValues) => void
  idPrefix?: string
}>): React.JSX.Element | null {
  if (fields.length === 0) return null
  return (
    <>
      {fields.map((field) => {
        const id = `${idPrefix}-${field.key}`
        const value = values[field.key] ?? ''
        const setValue = (next: string): void => {
          onChange({ ...values, [field.key]: next })
        }
        return (
          <div key={field.key} className="space-y-2">
            <Label htmlFor={id}>
              {field.label}
              {field.required ? <span className="ml-1 text-destructive">*</span> : null}
            </Label>
            {field.type === 'select' ? (
              <Select value={value} onValueChange={setValue}>
                <SelectTrigger id={id}>
                  <SelectValue placeholder={field.placeholder ?? '请选择'} />
                </SelectTrigger>
                <SelectContent>
                  {(field.options ?? []).map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            ) : field.type === 'textarea' ? (
              <Textarea
                id={id}
                value={value}
                onChange={(e) => {
                  setValue(e.target.value)
                }}
                placeholder={field.placeholder}
                className="min-h-[120px] font-mono text-xs"
              />
            ) : (
              <Input
                id={id}
                type={
                  field.type === 'password' ? 'password' : field.type === 'url' ? 'url' : 'text'
                }
                value={value}
                onChange={(e) => {
                  setValue(e.target.value)
                }}
                placeholder={field.placeholder}
              />
            )}
            {field.helpText ? (
              <p className="text-[11px] text-muted-foreground">{field.helpText}</p>
            ) : null}
          </div>
        )
      })}
    </>
  )
}
