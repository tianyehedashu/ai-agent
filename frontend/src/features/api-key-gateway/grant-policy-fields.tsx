/**
 * 平台 API Key Gateway grant 策略字段（RPM/TPM/能力/模型等）
 */

import type React from 'react'

import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'

import { GATEWAY_PROXY_CAPABILITIES, type GrantPolicyValues } from './gateway-capability-options'

interface GrantPolicyFieldsProps {
  values: GrantPolicyValues
  onChange: (values: GrantPolicyValues) => void
  idPrefix?: string
}

export function GrantPolicyFields({
  values,
  onChange,
  idPrefix = 'grant',
}: GrantPolicyFieldsProps): React.ReactElement {
  const patch = (partial: Partial<GrantPolicyValues>): void => {
    onChange({ ...values, ...partial })
  }

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor={`${idPrefix}-models`}>允许模型 ID（逗号分隔，留空不限）</Label>
        <Input
          id={`${idPrefix}-models`}
          placeholder="gpt-4o, claude-3-5-sonnet"
          value={values.allowed_models.join(', ')}
          onChange={(e) => {
            const models = e.target.value
              .split(',')
              .map((s) => s.trim())
              .filter(Boolean)
            patch({ allowed_models: models })
          }}
        />
      </div>

      <div className="space-y-2">
        <Label>允许能力（留空表示不限制）</Label>
        <div className="grid gap-2 sm:grid-cols-2">
          {GATEWAY_PROXY_CAPABILITIES.map((cap) => (
            <div key={cap.value} className="flex items-center gap-2">
              <Checkbox
                id={`${idPrefix}-cap-${cap.value}`}
                checked={values.allowed_capabilities.includes(cap.value)}
                onCheckedChange={(checked) => {
                  const next = checked
                    ? [...values.allowed_capabilities, cap.value]
                    : values.allowed_capabilities.filter((v) => v !== cap.value)
                  patch({ allowed_capabilities: next })
                }}
              />
              <label htmlFor={`${idPrefix}-cap-${cap.value}`} className="cursor-pointer text-sm">
                {cap.label}
              </label>
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <Label htmlFor={`${idPrefix}-rpm`}>RPM 上限（留空不限）</Label>
          <Input
            id={`${idPrefix}-rpm`}
            type="number"
            min={1}
            value={values.rpm_limit ?? ''}
            onChange={(e) => {
              patch({
                rpm_limit: e.target.value ? Number(e.target.value) : null,
              })
            }}
          />
        </div>
        <div>
          <Label htmlFor={`${idPrefix}-tpm`}>TPM 上限（留空不限）</Label>
          <Input
            id={`${idPrefix}-tpm`}
            type="number"
            min={1}
            value={values.tpm_limit ?? ''}
            onChange={(e) => {
              patch({
                tpm_limit: e.target.value ? Number(e.target.value) : null,
              })
            }}
          />
        </div>
      </div>

      <div className="flex items-center justify-between gap-4">
        <Label htmlFor={`${idPrefix}-store`} className="flex flex-col gap-1">
          <span>记录完整消息</span>
          <span className="text-xs font-normal text-muted-foreground">关闭后仅存元数据</span>
        </Label>
        <Switch
          id={`${idPrefix}-store`}
          checked={values.store_full_messages}
          onCheckedChange={(v) => {
            patch({ store_full_messages: v })
          }}
        />
      </div>

      <div className="flex items-center justify-between gap-4">
        <Label htmlFor={`${idPrefix}-guardrail`} className="flex flex-col gap-1">
          <span>PII 脱敏护栏</span>
          <span className="text-xs font-normal text-muted-foreground">需平台全局开启</span>
        </Label>
        <Switch
          id={`${idPrefix}-guardrail`}
          checked={values.guardrail_enabled}
          onCheckedChange={(v) => {
            patch({ guardrail_enabled: v })
          }}
        />
      </div>
    </div>
  )
}
