import { useMemo, useState } from 'react'

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
import { Check, ChevronsUpDown, Loader2 } from '@/lib/lucide-icons'
import { cn } from '@/lib/utils'

import {
  BUDGET_MODEL_GROUP_LABELS,
  BUDGET_MODEL_GROUP_ORDER,
  budgetModelOptionLabel,
  budgetModelOptionsByName,
  groupBudgetModelOptions,
  type BudgetModelOption,
} from './budget-model-options'

const ALL_MODELS_VALUE = '__all__'

export interface BudgetModelComboboxProps {
  value: string
  onChange: (modelName: string) => void
  options: readonly BudgetModelOption[]
  disabled?: boolean
  loading?: boolean
  placeholder?: string
  className?: string
  id?: string
  onPopoverOpenChange?: (open: boolean) => void
}

function commandItemValue(option: BudgetModelOption): string {
  return [option.name, option.provider, option.capability, option.group].filter(Boolean).join(' ')
}

export function BudgetModelCombobox({
  value,
  onChange,
  options,
  disabled = false,
  loading = false,
  placeholder = '全模型汇总',
  className,
  id,
  onPopoverOpenChange,
}: Readonly<BudgetModelComboboxProps>): React.JSX.Element {
  const [open, setOpen] = useState(false)

  const handleOpenChange = (next: boolean): void => {
    setOpen(next)
    onPopoverOpenChange?.(next)
  }

  const grouped = useMemo(() => groupBudgetModelOptions(options), [options])
  const optionsByName = useMemo(() => budgetModelOptionsByName(options), [options])

  const trimmedValue = value.trim()
  const selectedOption = trimmedValue === '' ? null : (optionsByName.get(trimmedValue) ?? null)
  const triggerLabel = loading
    ? '加载模型…'
    : trimmedValue === ''
      ? placeholder
      : (selectedOption?.name ?? trimmedValue)
  const triggerDisabled = disabled || loading

  return (
    <Popover open={open} onOpenChange={handleOpenChange}>
      <PopoverTrigger asChild>
        <Button
          id={id}
          type="button"
          variant="outline"
          role="combobox"
          aria-expanded={open}
          disabled={triggerDisabled}
          className={cn('w-full justify-between font-normal', className)}
        >
          <span className="flex min-w-0 items-center gap-2 truncate">
            {loading ? <Loader2 className="h-4 w-4 shrink-0 animate-spin opacity-60" /> : null}
            <span className="truncate">{triggerLabel}</span>
          </span>
          <ChevronsUpDown className="h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[var(--radix-popover-trigger-width)] p-0" align="start">
        <Command>
          <CommandInput placeholder="搜索模型别名、通道…" />
          <CommandList>
            <CommandEmpty>未找到匹配的模型</CommandEmpty>
            <CommandGroup heading="汇总">
              <CommandItem
                value={ALL_MODELS_VALUE}
                onSelect={() => {
                  onChange('')
                  setOpen(false)
                }}
              >
                <Check
                  className={cn('mr-2 h-4 w-4', trimmedValue === '' ? 'opacity-100' : 'opacity-0')}
                />
                {placeholder}
              </CommandItem>
            </CommandGroup>
            {BUDGET_MODEL_GROUP_ORDER.map((group) => {
              const items = grouped[group]
              if (items.length === 0) return null
              return (
                <CommandGroup key={group} heading={BUDGET_MODEL_GROUP_LABELS[group]}>
                  {items.map((option) => (
                    <CommandItem
                      key={`${group}-${option.name}`}
                      value={commandItemValue(option)}
                      className="[contain-intrinsic-size:0_44px] [content-visibility:auto]"
                      onSelect={() => {
                        onChange(option.name)
                        setOpen(false)
                      }}
                    >
                      <Check
                        className={cn(
                          'mr-2 h-4 w-4',
                          value === option.name ? 'opacity-100' : 'opacity-0'
                        )}
                      />
                      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                        <span className="truncate">{option.name}</span>
                        <span className="text-[11px] text-muted-foreground">
                          {budgetModelOptionLabel(option)}
                        </span>
                      </div>
                    </CommandItem>
                  ))}
                </CommandGroup>
              )
            })}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}

export function BudgetModelComboboxHint({
  loading,
  optionsCount,
}: {
  loading: boolean
  optionsCount: number
}): React.JSX.Element | null {
  if (loading || optionsCount > 0) return null
  return <p className="text-[11px] text-muted-foreground">暂无可用模型，请先在模型管理中注册。</p>
}
