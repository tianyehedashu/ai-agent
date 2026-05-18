import type { GatewayUsageAggregation } from '@/api/gateway'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

import { GATEWAY_USAGE_AGGREGATION_OPTIONS } from './usage-aggregation'

export type UsageAggregationToggleSize = 'default' | 'compact'

export interface UsageAggregationToggleProps {
  value: GatewayUsageAggregation
  onChange: (value: GatewayUsageAggregation) => void
  size?: UsageAggregationToggleSize
  className?: string
}

const BUTTON_CLASS: Record<UsageAggregationToggleSize, string> = {
  default: 'h-7 px-3 text-xs',
  compact: 'h-7 px-2 text-xs',
}

/** 用量切片「团�?/ 我」切换；文案来自 ``GATEWAY_USAGE_AGGREGATION_OPTIONS``�?*/
export function UsageAggregationToggle({
  value,
  onChange,
  size = 'default',
  className,
}: UsageAggregationToggleProps): React.JSX.Element {
  const buttonClass = BUTTON_CLASS[size]
  return (
    <div
      className={cn(
        'flex w-fit items-center gap-1 rounded-md border bg-background p-0.5',
        className
      )}
    >
      {GATEWAY_USAGE_AGGREGATION_OPTIONS.map((option) => (
        <Button
          key={option.value}
          type="button"
          size="sm"
          variant={value === option.value ? 'default' : 'ghost'}
          className={buttonClass}
          title={option.description}
          onClick={() => {
            onChange(option.value)
          }}
        >
          {option.label}
        </Button>
      ))}
    </div>
  )
}
