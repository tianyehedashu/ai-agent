import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  ROUTING_STRATEGIES,
  routingStrategyLabel,
  type RoutingStrategy,
} from '@/features/gateway-models/constants'

interface RoutingStrategySelectProps {
  value: string
  onValueChange: (value: RoutingStrategy) => void
  disabled?: boolean
  className?: string
}

export function RoutingStrategySelect({
  value,
  onValueChange,
  disabled = false,
  className,
}: RoutingStrategySelectProps): React.JSX.Element {
  return (
    <Select
      value={value}
      onValueChange={(v) => {
        onValueChange(v as RoutingStrategy)
      }}
      disabled={disabled}
    >
      <SelectTrigger className={className}>
        <SelectValue placeholder="选择策略" />
      </SelectTrigger>
      <SelectContent>
        {ROUTING_STRATEGIES.map((strategy) => (
          <SelectItem key={strategy} value={strategy}>
            <span className="flex w-full items-baseline gap-2">
              <span>{routingStrategyLabel(strategy)}</span>
              <span className="font-mono text-xs text-muted-foreground">{strategy}</span>
            </span>
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
