import { memo, type ReactNode } from 'react'

import { Link } from 'react-router-dom'

import type { GatewayModel, GatewayModelRouteUsageItem } from '@/api/gateway'
import { ModelStatusBadge } from '@/components/model-status-badge'
import { Checkbox } from '@/components/ui/checkbox'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { cn, formatRelativeTime } from '@/lib/utils'

import { channelLabel, classifyFailureReason, formatUsageLine } from '../utils'
import { ModelCapabilityBadges } from './model-capability-badges'
import { SystemModelAdminMeta } from './system-model-admin-meta'

import type { UsagePeriodDays } from '../constants'

const CONFIG_MANAGED_BATCH_HINT =
  '配置同步托管的系统模型不可删除；请通过 gateway-catalog 或配置管理'

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
  trailingActions?: ReactNode
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
  trailingActions,
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
    <li
      data-connectivity-model-id={model.id}
      className="[contain-intrinsic-size:auto_2.75rem] [content-visibility:auto]"
    >
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
            {batchSelectable ? (
              <Checkbox
                checked={batchSelected}
                aria-label={`选择模型 ${model.name}`}
                onCheckedChange={(checked) => {
                  onBatchSelectChange?.(model.id, checked === true)
                }}
              />
            ) : (
              <TooltipProvider delayDuration={300}>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <span tabIndex={0}>
                      <Checkbox checked={false} disabled aria-label={`不可选择 ${model.name}`} />
                    </span>
                  </TooltipTrigger>
                  <TooltipContent className="max-w-xs text-xs">
                    {configManaged ? CONFIG_MANAGED_BATCH_HINT : '无删除权限'}
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            )}
          </div>
        ) : null}
        {mainRow}
        {trailingActions ? (
          <div
            className="flex shrink-0 items-center gap-1 border-l px-2"
            onClick={(e) => {
              e.preventDefault()
              e.stopPropagation()
            }}
            onKeyDown={(e) => {
              e.stopPropagation()
            }}
            role="presentation"
          >
            {trailingActions}
          </div>
        ) : null}
      </div>
    </li>
  )
})
