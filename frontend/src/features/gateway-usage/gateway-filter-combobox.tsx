import { useMemo, useState } from 'react'
import type React from 'react'

import { Button } from '@/components/ui/button'
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { ChevronsUpDown, Loader2 } from '@/lib/lucide-icons'
import { cn } from '@/lib/utils'

/** 与调用统计页筛选「全部」取值一致 */
export const GATEWAY_FILTER_ALL = '__all__'

export interface GatewayFilterOption {
  value: string
  label: string
  meta?: string
}

function commandItemValue(option: GatewayFilterOption): string {
  return [option.label, option.meta, option.value].filter(Boolean).join(' ')
}

export interface GatewayFilterComboboxProps {
  value: string
  onChange: (value: string) => void
  options: readonly GatewayFilterOption[]
  placeholder?: string
  allLabel?: string
  searchPlaceholder?: string
  loading?: boolean
  disabled?: boolean
  className?: string
  id?: string
  onOpenChange?: (open: boolean) => void
}

export function GatewayFilterCombobox({
  value,
  onChange,
  options,
  placeholder = '全部',
  allLabel = '全部',
  searchPlaceholder = '搜索…',
  loading = false,
  disabled = false,
  className,
  id,
  onOpenChange,
}: Readonly<GatewayFilterComboboxProps>): React.JSX.Element {
  const [open, setOpen] = useState(false)

  const handleOpenChange = (next: boolean): void => {
    setOpen(next)
    onOpenChange?.(next)
  }

  const optionsByValue = useMemo(
    () => new Map(options.map((option) => [option.value, option])),
    [options]
  )

  const isAll = value === GATEWAY_FILTER_ALL
  const selected = isAll ? null : (optionsByValue.get(value) ?? null)
  const triggerLabel = loading ? '加载中…' : isAll ? placeholder : (selected?.label ?? value)

  return (
    <Popover open={open} onOpenChange={handleOpenChange}>
      <PopoverTrigger asChild>
        <Button
          id={id}
          type="button"
          variant="outline"
          role="combobox"
          aria-expanded={open}
          disabled={disabled || loading}
          className={cn('h-9 min-w-[140px] justify-between text-xs font-normal', className)}
        >
          <span className="flex min-w-0 items-center gap-2 truncate">
            {loading ? <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin opacity-60" /> : null}
            <span className="truncate">{triggerLabel}</span>
          </span>
          <ChevronsUpDown className="h-3.5 w-3.5 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent
        className="w-[min(20rem,var(--radix-popover-trigger-width))] p-0"
        align="start"
        side="bottom"
        collisionPadding={8}
      >
        <Command>
          <CommandInput placeholder={searchPlaceholder} />
          <CommandList>
            <CommandEmpty>未找到匹配项</CommandEmpty>
            <CommandGroup>
              <CommandItem
                value={GATEWAY_FILTER_ALL}
                onSelect={() => {
                  onChange(GATEWAY_FILTER_ALL)
                  setOpen(false)
                }}
              >
                {allLabel}
              </CommandItem>
              {options.map((option) => (
                <CommandItem
                  key={option.value}
                  value={commandItemValue(option)}
                  className="[contain-intrinsic-size:0_40px] [content-visibility:auto]"
                  onSelect={() => {
                    onChange(option.value)
                    setOpen(false)
                  }}
                >
                  <div className="flex min-w-0 flex-col gap-0.5">
                    <span className="truncate">{option.label}</span>
                    {option.meta ? (
                      <span className="truncate text-[11px] text-muted-foreground">
                        {option.meta}
                      </span>
                    ) : null}
                  </div>
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}
