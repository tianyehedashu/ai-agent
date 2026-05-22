import { memo } from 'react'

import { Link } from 'react-router-dom'

import type { GatewayModel, GatewayModelRouteUsageItem } from '@/api/gateway'
import { ModelStatusBadge } from '@/components/model-status-badge'
import { Checkbox } from '@/components/ui/checkbox'
import { cn, formatRelativeTime } from '@/lib/utils'

import { channelLabel, classifyFailureReason, formatUsageLine } from '../utils'
import { ModelCapabilityBadges } from './model-capability-badges'
import { SystemModelAdminMeta } from './system-model-admin-meta'

import type { UsagePeriodDays } from '../constants'

interface ModelInventoryRowProps {
  model: GatewayModel
  selected: boolean
  highlighted: boolean
  usageDays: UsagePeriodDays
  usageRow: GatewayModelRouteUsageItem | undefined
  usageLoading: boolean
  /** 有则整行渲染为 Link（凭据详情等深链场景）；无则 button + onSelect */
  href?: string
  onSelect?: (id: string) => void
  onPreloadNavigate?: () => void
  showSystemAdmin?: boolean
  batchSelectEnabled?: boolean
  batchSelected?: boolean
  batchSelectable?: boolean
  onBatchSelectChange?: (id: string, selected: boolean) => void
  canDelete?: boolean
  configManaged?: boolean
  isDeleting?: boolean
  onDelete?: (id: string) => void
}

export const ModelInventoryRow = memo(function ModelInventoryRow({
  model,
  selected,
  highlighted,
  usageDays,
  usageRow,
  usageLoading,
  href,
  onSelect,
  onPreloadNavigate,
  showSystemAdmin = false,
  batchSelectEnabled = false,
  batchSelected = false,
  batchSelectable = false,
  onBatchSelectChange,
  canDelete = false,
  configManaged = false,
  isDeleting = false,
  onDelete,
}: ModelInventoryRowProps): React.JSX.Element {
  const wsReq = usageRow?.workspace.requests ?? 0
  const wsTok = (usageRow?.workspace.input_tokens ?? 0) + (usageRow?.workspace.output_tokens ?? 0)
  const usageText =
    !usageLoading && usageRow
      ? formatUsageLine(usageDays, wsReq, wsTok, usageRow.workspace.cost_usd)
      : null
  const failShort =
    model.last_test_status === 'failed' ? classifyFailureReason(model.last_test_reason) : null
  const testedRelative =
    model.last_tested_at && model.last_test_status !== null
      ? formatRelativeTime(model.last_tested_at)
      : null

  const rowClassName = cn(
    'block w-full px-3 py-2.5 text-left transition-colors hover:bg-muted/40',
    selected && 'bg-primary/10',
    highlighted && !selected && 'bg-primary/5'
  )

  const rowContent = (
    <>
      <div className="flex min-w-0 items-center gap-2">
        <p className="min-w-0 flex-1 truncate font-mono text-sm font-medium">{model.name}</p>
        <ModelStatusBadge
          status={model.last_test_status}
          testedAt={model.last_tested_at}
          reason={model.last_test_reason}
          compact
        />
      </div>
      <p className="mt-0.5 flex min-w-0 items-baseline gap-1.5 text-xs text-muted-foreground">
        <span className="min-w-0 truncate">
          {channelLabel(model.provider)} · {model.real_model}
        </span>
        {testedRelative ? (
          <span className="shrink-0 tabular-nums text-muted-foreground/70">{testedRelative}</span>
        ) : null}
      </p>
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
      {showSystemAdmin ? (
        <SystemModelAdminMeta
          model={model}
          canDelete={canDelete}
          configManaged={configManaged}
          isDeleting={isDeleting}
          onDelete={
            onDelete
              ? () => {
                  onDelete(model.id)
                }
              : undefined
          }
        />
      ) : null}
    </>
  )

  const mainRow = href ? (
    <Link
      to={href}
      className={cn(rowClassName, 'min-w-0 flex-1')}
      onMouseEnter={onPreloadNavigate}
      onFocus={onPreloadNavigate}
    >
      {rowContent}
    </Link>
  ) : (
    <button
      type="button"
      onClick={() => {
        onSelect?.(model.id)
      }}
      className={cn(rowClassName, 'min-w-0 flex-1')}
    >
      {rowContent}
    </button>
  )

  return (
    <li className="[contain-intrinsic-size:auto_2.75rem] [content-visibility:auto]">
      <div className="flex items-stretch">
        {batchSelectEnabled ? (
          <div
            className="flex shrink-0 items-start px-2 pt-3"
            onClick={(e) => {
              e.preventDefault()
              e.stopPropagation()
            }}
            onKeyDown={(e) => {
              e.stopPropagation()
            }}
            role="presentation"
          >
            <Checkbox
              checked={batchSelected}
              disabled={!batchSelectable}
              aria-label={`选择模型 ${model.name}`}
              onCheckedChange={(checked) => {
                onBatchSelectChange?.(model.id, checked === true)
              }}
            />
          </div>
        ) : null}
        {mainRow}
      </div>
    </li>
  )
})
