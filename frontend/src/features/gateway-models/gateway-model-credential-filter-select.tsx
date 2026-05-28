import type React from 'react'

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { FILTER_ALL } from '@/features/gateway-models/constants'
import { channelLabel } from '@/features/gateway-models/utils'
import { cn } from '@/lib/utils'

export interface GatewayModelCredentialFilterOption {
  id: string
  name: string
  provider?: string
  teamLabel?: string
}

export interface GatewayModelCredentialFilterSelectProps {
  value: string
  onChange: (credentialId: string) => void
  options: readonly GatewayModelCredentialFilterOption[]
  loading?: boolean
  disabled?: boolean
  className?: string
  triggerClassName?: string
  ariaLabel?: string
}

function optionLabel(option: GatewayModelCredentialFilterOption): string {
  const base = option.provider ? `${option.name} · ${channelLabel(option.provider)}` : option.name
  if (option.teamLabel) {
    return `${option.teamLabel} · ${base}`
  }
  return base
}

export function GatewayModelCredentialFilterSelect({
  value,
  onChange,
  options,
  loading = false,
  disabled = false,
  className,
  triggerClassName,
  ariaLabel = '按凭据筛选',
}: Readonly<GatewayModelCredentialFilterSelectProps>): React.JSX.Element {
  const selectValue = value || FILTER_ALL

  return (
    <Select
      value={selectValue}
      onValueChange={(v) => {
        onChange(v === FILTER_ALL ? '' : v)
      }}
      disabled={disabled || loading}
    >
      <SelectTrigger
        className={cn('h-8 w-[160px] shrink-0 text-xs', triggerClassName, className)}
        aria-label={ariaLabel}
      >
        <SelectValue placeholder={loading ? '加载凭据…' : '全部凭据'} />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={FILTER_ALL}>全部凭据</SelectItem>
        {options.map((option) => (
          <SelectItem key={option.id} value={option.id}>
            {optionLabel(option)}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
