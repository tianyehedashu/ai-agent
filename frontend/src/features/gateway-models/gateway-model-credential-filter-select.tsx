import { useMemo } from 'react'
import type React from 'react'

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { FILTER_ALL } from '@/features/gateway-models/constants'
import {
  formatGatewayModelCredentialFilterLabel,
  type GatewayModelCredentialFilterOption,
} from '@/features/gateway-models/gateway-model-credential-filter-label'
import { cn } from '@/lib/utils'

export interface GatewayModelCredentialFilterSelectProps {
  value: string
  onChange: (credentialId: string) => void
  options: readonly GatewayModelCredentialFilterOption[]
  loading?: boolean
  disabled?: boolean
  className?: string
  triggerClassName?: string
  ariaLabel?: string
  /** options 未加载或未命中时，用列表行上的凭据名展示 trigger */
  selectedCredentialName?: string | null
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
  selectedCredentialName,
}: Readonly<GatewayModelCredentialFilterSelectProps>): React.JSX.Element {
  const selectValue = value || FILTER_ALL

  const selectedOption = useMemo(
    () => (value ? options.find((option) => option.id === value) : undefined),
    [options, value]
  )

  const triggerLabel = useMemo((): string | undefined => {
    if (!value) return undefined
    if (selectedOption) return formatGatewayModelCredentialFilterLabel(selectedOption)
    const name = selectedCredentialName?.trim()
    if (name) return name
    if (loading) return '加载凭据…'
    return undefined
  }, [value, selectedOption, selectedCredentialName, loading])

  return (
    <Select
      value={selectValue}
      onValueChange={(v) => {
        onChange(v === FILTER_ALL ? '' : v)
      }}
      disabled={disabled || loading}
    >
      <SelectTrigger
        className={cn(
          'h-8 min-w-[160px] max-w-[280px] shrink-0 text-xs',
          triggerClassName,
          className
        )}
        aria-label={ariaLabel}
      >
        <SelectValue placeholder={loading ? '加载凭据…' : '全部凭据'}>{triggerLabel}</SelectValue>
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={FILTER_ALL}>全部凭据</SelectItem>
        {options.map((option) => (
          <SelectItem key={option.id} value={option.id}>
            {formatGatewayModelCredentialFilterLabel(option)}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
