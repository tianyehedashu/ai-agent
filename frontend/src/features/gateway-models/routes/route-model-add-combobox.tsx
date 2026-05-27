import { memo, useCallback, useRef, useState } from 'react'

import type { GatewayModel, MyPriceRow } from '@/api/gateway'
import { ModelStatusBadge } from '@/components/model-status-badge'
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
import { GATEWAY_DISPLAY_CURRENCY } from '@/features/gateway-pricing/display-currency'
import { PricingBadge } from '@/features/gateway-pricing/pricing-badge'
import { Plus } from '@/lib/lucide-icons'
import { cn } from '@/lib/utils'
import type { DisplayCurrency } from '@/types/money'

export interface RouteModelAddComboboxProps {
  candidates: readonly GatewayModel[]
  onPick: (name: string) => void
  disabled?: boolean
  triggerLabel: string
  emptyMessage?: string
  variant?: 'default' | 'outline' | 'ghost'
  size?: 'default' | 'sm'
  className?: string
  priceByName?: Map<string, MyPriceRow>
  currency?: DisplayCurrency
}

function commandItemValue(model: GatewayModel): string {
  return [model.name, model.provider, model.real_model, model.capability].filter(Boolean).join(' ')
}

export const RouteModelAddCombobox = memo(function RouteModelAddCombobox({
  candidates,
  onPick,
  disabled = false,
  triggerLabel,
  emptyMessage = '未找到匹配的模型',
  variant = 'outline',
  size = 'sm',
  className,
  priceByName,
  currency = GATEWAY_DISPLAY_CURRENCY,
}: Readonly<RouteModelAddComboboxProps>): React.JSX.Element {
  const [open, setOpen] = useState(false)
  const onPickRef = useRef(onPick)
  onPickRef.current = onPick

  const triggerDisabled = disabled || candidates.length === 0

  const handlePick = useCallback((name: string): void => {
    onPickRef.current(name)
    setOpen(false)
  }, [])

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant={variant}
          size={size}
          disabled={triggerDisabled}
          className={cn('gap-1.5', className)}
        >
          <Plus className="h-3.5 w-3.5" aria-hidden="true" />
          {triggerLabel}
        </Button>
      </PopoverTrigger>
      <PopoverContent
        className="w-[min(24rem,var(--radix-popover-trigger-width))] p-0"
        align="start"
      >
        {open ? (
          <Command>
            <CommandInput placeholder="搜索模型别名、通道…" />
            <CommandList>
              <CommandEmpty>{emptyMessage}</CommandEmpty>
              <CommandGroup>
                {candidates.map((model) => (
                  <CommandItem
                    key={model.id}
                    value={commandItemValue(model)}
                    className="[contain-intrinsic-size:0_44px] [content-visibility:auto]"
                    onSelect={() => {
                      handlePick(model.name)
                    }}
                  >
                    <div className="flex min-w-0 flex-1 items-center gap-2">
                      <span className="min-w-0 flex-1 truncate font-mono text-sm">
                        {model.name}
                      </span>
                      <PricingBadge
                        row={priceByName?.get(model.name)}
                        currency={currency}
                        className="hidden shrink-0 sm:inline"
                      />
                      <ModelStatusBadge
                        status={model.last_test_status}
                        testedAt={model.last_tested_at}
                        reason={model.last_test_reason}
                        entitlementStatus={model.entitlement_status}
                        entitlementResetAt={model.entitlement_reset_at}
                        compact
                        withProvider={false}
                      />
                    </div>
                  </CommandItem>
                ))}
              </CommandGroup>
            </CommandList>
          </Command>
        ) : null}
      </PopoverContent>
    </Popover>
  )
})
