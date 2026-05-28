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

type ModelInventoryRowLayout = 'stacked' | 'compact'

/** stacked：主从分栏清单；compact：分组列表单行信息密度更高 */
type ConnectivityDisplay = 'always' | 'attention-only'

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
  layout?: ModelInventoryRowLayout
  /** attention-only：探活成功时不展示「可用」徽标，减少重复视觉噪音 */
  connectivityDisplay?: ConnectivityDisplay
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
  layout = 'stacked',
  connectivityDisplay = 'always',
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

  const isCompact = layout === 'compact'
  const showConnectivityBadge =
    connectivityDisplay === 'always' || model.last_test_status !== 'success'

  const rowClassName = cn(
    'block w-full text-left transition-colors',
    isCompact ? 'px-3 py-2' : 'px-3 py-2.5',
    'hover:bg-muted/40',
    selected && 'bg-primary/10',
    highlighted && !selected && 'bg-primary/5'
  )

  const metaLine = (
    <p className="flex min-w-0 items-baseline gap-1.5 text-xs text-muted-foreground">
      <span className="min-w-0 truncate">
        {channelLabel(model.provider)} · {model.real_model}
      </span>
      {testedRelative ? (
        <span className="shrink-0 tabular-nums text-muted-foreground/80">{testedRelative}</span>
      ) : null}
    </p>
  )

  const statusBadge = showConnectivityBadge ? (
    <ModelStatusBadge
      status={model.last_test_status}
      testedAt={model.last_tested_at}
      reason={model.last_test_reason}
      compact
      withProvider={false}
    />
  ) : null

  const stackedRowContent = (
    <>
      <div className="flex min-w-0 items-center gap-2">
        <p className="min-w-0 flex-1 truncate font-mono text-sm font-medium">{model.name}</p>
        {statusBadge}
      </div>
      {metaLine}
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

  const compactRowContent = (
    <div className="min-w-0 space-y-1.5">
      <p className="truncate font-mono text-sm font-medium leading-snug">{model.name}</p>
      {metaLine}
      {failShort ? <p className="text-xs text-destructive">{failShort}</p> : null}
      {!model.enabled ? (
        <p className="text-xs font-medium text-amber-600 dark:text-amber-400">已禁用</p>
      ) : null}
      <ModelCapabilityBadges model={model} compact />
    </div>
  )

  const rowContent = isCompact ? compactRowContent : stackedRowContent

  const hasTrailing = trailingActions !== null
  const mainRowClassName = cn(rowClassName, 'min-w-0 overflow-hidden', hasTrailing && 'block')

  const mainRow = href ? (
    <Link
      to={href}
      className={mainRowClassName}
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
      className={mainRowClassName}
    >
      {rowContent}
    </button>
  )

  const trailingCell = hasTrailing ? (
    <div
      className={cn(
        'sticky right-0 z-[1] flex shrink-0 items-center gap-2 border-l border-border/60 bg-card px-2.5 py-2 shadow-[-10px_0_12px_-10px_hsl(var(--background)/0.9)]',
        'group-hover:bg-muted/30 sm:px-3'
      )}
      onClick={(e) => {
        e.preventDefault()
        e.stopPropagation()
      }}
      onKeyDown={(e) => {
        e.stopPropagation()
      }}
      role="presentation"
    >
      {statusBadge}
      {trailingActions}
    </div>
  ) : statusBadge ? (
    <div className="flex shrink-0 items-center px-3 py-2">{statusBadge}</div>
  ) : null

  const rowGridClassName = cn(
    'grid w-full min-w-0 items-stretch',
    batchSelectEnabled && hasTrailing && 'grid-cols-[auto_minmax(0,1fr)_auto]',
    batchSelectEnabled && !hasTrailing && 'grid-cols-[auto_minmax(0,1fr)]',
    !batchSelectEnabled && hasTrailing && 'grid-cols-[minmax(0,1fr)_auto]',
    !batchSelectEnabled && !hasTrailing && 'grid-cols-[minmax(0,1fr)]'
  )

  return (
    <li
      data-connectivity-model-id={model.id}
      className={cn(
        'group',
        !hasTrailing && '[contain-intrinsic-size:auto_2.75rem] [content-visibility:auto]'
      )}
    >
      <div className={rowGridClassName}>
        {batchSelectEnabled ? (
          <div
            className={cn(
              'flex shrink-0 items-center justify-center px-2',
              !isCompact && 'items-start pt-3'
            )}
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
        {trailingCell}
      </div>
    </li>
  )
})
