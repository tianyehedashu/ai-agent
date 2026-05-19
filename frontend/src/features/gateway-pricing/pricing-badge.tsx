import type React from 'react'

import type { MyPriceRow } from '@/api/gateway'
import { formatRateLine } from '@/features/gateway-pricing/format'
import { cn } from '@/lib/utils'
import type { DisplayCurrency } from '@/types/money'

interface PricingBadgeProps {
  row: MyPriceRow | null | undefined
  currency: DisplayCurrency
  className?: string
}

export function PricingBadge({
  row,
  currency,
  className,
}: PricingBadgeProps): React.JSX.Element | null {
  if (!row) return null
  const line = formatRateLine(
    row.input_cost_per_million_display,
    row.output_cost_per_million_display,
    currency
  )
  return (
    <span
      className={cn('text-xs tabular-nums text-muted-foreground', className)}
      title={row.inheritance_strategy === 'mirror' ? '价格跟随上游成本' : undefined}
    >
      {line}
    </span>
  )
}
