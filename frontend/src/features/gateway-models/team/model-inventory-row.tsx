import { memo } from 'react'

import type { GatewayModel, GatewayModelRouteUsageItem } from '@/api/gateway'
import { ModelStatusBadge } from '@/components/model-status-badge'
import { cn } from '@/lib/utils'

import { channelLabel, classifyFailureReason, formatUsageLine } from '../utils'
import { ModelCapabilityBadges } from './model-capability-badges'

import type { UsagePeriodDays } from '../constants'

interface ModelInventoryRowProps {
  model: GatewayModel
  selected: boolean
  highlighted: boolean
  usageDays: UsagePeriodDays
  usageRow: GatewayModelRouteUsageItem | undefined
  usageLoading: boolean
  onSelect: (id: string) => void
}

export const ModelInventoryRow = memo(function ModelInventoryRow({
  model,
  selected,
  highlighted,
  usageDays,
  usageRow,
  usageLoading,
  onSelect,
}: ModelInventoryRowProps): React.JSX.Element {
  const wsReq = usageRow?.workspace.requests ?? 0
  const wsTok = (usageRow?.workspace.input_tokens ?? 0) + (usageRow?.workspace.output_tokens ?? 0)
  const usageText =
    !usageLoading && usageRow
      ? formatUsageLine(usageDays, wsReq, wsTok, usageRow.workspace.cost_usd)
      : null
  const failShort =
    model.last_test_status === 'failed' ? classifyFailureReason(model.last_test_reason) : null

  return (
    <li className="[contain-intrinsic-size:auto_2.75rem] [content-visibility:auto]">
      <button
        type="button"
        onClick={() => {
          onSelect(model.id)
        }}
        className={cn(
          'w-full px-3 py-2.5 text-left transition-colors hover:bg-muted/40',
          selected && 'bg-primary/10',
          highlighted && !selected && 'bg-primary/5'
        )}
      >
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <p className="truncate font-mono text-sm font-medium">{model.name}</p>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {channelLabel(model.provider)} · {model.real_model}
            </p>
          </div>
          <ModelStatusBadge
            status={model.last_test_status}
            testedAt={model.last_tested_at}
            reason={model.last_test_reason}
            className="shrink-0"
          />
        </div>
        {failShort ? <p className="mt-1 text-xs text-destructive">{failShort}</p> : null}
        {usageLoading ? (
          <p className="mt-1 text-xs text-muted-foreground">用量…</p>
        ) : usageText ? (
          <p className="mt-1 text-xs tabular-nums text-muted-foreground">{usageText}</p>
        ) : null}
        <div className="mt-1.5">
          <ModelCapabilityBadges model={model} compact />
        </div>
        {!model.enabled ? (
          <p className="mt-1 text-xs text-amber-600 dark:text-amber-400">已禁用</p>
        ) : null}
      </button>
    </li>
  )
})
