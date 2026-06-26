import { memo } from 'react'

import { Link } from 'react-router-dom'

import type { GatewayModel } from '@/api/gateway/models'
import { ModelStatusBadge } from '@/components/model-status-badge'
import { Badge } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/checkbox'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { cn, formatRelativeTime } from '@/lib/utils'

import { CopyableText } from '../components/copyable-text'
import { ModelAffiliationCell } from '../components/model-affiliation-cell'
import { modelTypeLabel } from '../constants'
import {
  contextWindowBadgeLabel,
  listContextWindowLabel,
  resolveContextWindow,
} from '../context-window-display'
import {
  clientInvokeModelName,
  listCapabilityLabel,
  listCapabilityFullLabel,
  listCredentialName,
  listDisplayName,
  upstreamChannelLabel,
} from './model-list-columns'
import { ModelCapabilityBadges } from '../team/model-capability-badges'
import { SystemModelAdminMeta } from '../team/system-model-admin-meta'
import { classifyFailureReason, formatUsageLine } from '../utils'
import { ListCellText } from './list-cell-text'

import type { GatewayModelListRowProps } from './types'

const CONFIG_MANAGED_BATCH_HINT =
  '配置同步托管的系统模型不可删除；请通过 gateway-catalog 或配置管理'

function isGatewayModelSource(
  source: GatewayModelListRowProps['item']['source']
): source is GatewayModel {
  return 'real_model' in source
}

function PersonalTypeBadges({
  types,
  selectorCapabilities,
}: {
  types: readonly string[]
  selectorCapabilities?: Record<string, unknown>
}): React.JSX.Element | null {
  const contextLabel = contextWindowBadgeLabel(selectorCapabilities)
  if (types.length === 0 && !contextLabel) return null
  return (
    <div className="flex flex-wrap items-center gap-1">
      {types.map((t) => (
        <Badge key={t} variant="secondary" className="shrink-0 text-xs">
          {modelTypeLabel(t)}
        </Badge>
      ))}
      {contextLabel ? (
        <Badge variant="outline" className="shrink-0 text-xs font-normal">
          {contextLabel}
        </Badge>
      ) : null}
    </div>
  )
}

export const GatewayModelListRow = memo(function GatewayModelListRow({
  item,
  capabilities,
  selected = false,
  highlighted = false,
  showAffiliationColumn = false,
  teamNameById,
  usageDays = 7,
  usageRow,
  usageLoading = false,
  href,
  onSelect,
  onPreloadNavigate,
  batchSelected = false,
  onBatchSelectChange,
  canBatchSelect,
  isConfigManaged,
  canDelete,
  isDeleting = false,
  onDelete,
  trailingActions,
  columnsGrid,
}: GatewayModelListRowProps): React.JSX.Element {
  const isPersonal = item.scope === 'personal'
  const layout = capabilities.layout ?? 'compact'
  const connectivityDisplay = capabilities.connectivityDisplay ?? 'attention-only'
  const batchSelectEnabled = capabilities.batchSelect === true
  const showSystemAdmin = capabilities.showSystemAdmin === true && item.registryKind === 'system'

  const wsReq = usageRow?.workspace.requests ?? 0
  const wsTok = (usageRow?.workspace.input_tokens ?? 0) + (usageRow?.workspace.output_tokens ?? 0)
  const usageText =
    capabilities.usageSummary && !usageLoading && usageRow
      ? formatUsageLine(usageDays, wsReq, wsTok, usageRow.workspace.cost_usd)
      : null

  const failShort =
    item.lastTestStatus === 'failed' ? classifyFailureReason(item.lastTestReason) : null
  const testedRelative =
    item.lastTestedAt && item.lastTestStatus !== null ? formatRelativeTime(item.lastTestedAt) : null

  const isCompact = layout === 'compact'
  const isColumns = layout === 'columns'
  const showConnectivityBadge =
    connectivityDisplay === 'always' || item.lastTestStatus !== 'success'

  const configManaged = isConfigManaged?.(item) ?? false
  const batchSelectable = canBatchSelect?.(item) ?? false
  const rowCanDelete = canDelete?.(item) ?? false

  const rowClassName = cn(
    'block w-full text-left transition-colors',
    isCompact ? 'px-3 py-2' : 'px-3 py-2.5',
    'hover:bg-muted/40',
    selected && 'bg-primary/10',
    highlighted && !selected && 'bg-primary/5'
  )

  const statusBadge = showConnectivityBadge ? (
    <ModelStatusBadge
      status={item.lastTestStatus}
      testedAt={item.lastTestedAt}
      reason={item.lastTestReason}
      compact
      withProvider={false}
    />
  ) : null

  const personalMetaLines = isPersonal ? (
    <>
      {item.routeName ? (
        <p className="font-mono text-xs text-muted-foreground">{item.routeName}</p>
      ) : null}
      <p className="truncate text-xs text-muted-foreground">{item.upstreamModelId}</p>
    </>
  ) : (
    <p className="flex min-w-0 items-baseline gap-1.5 text-xs text-muted-foreground">
      <span className="min-w-0 truncate">{item.subtitle}</span>
      {testedRelative ? (
        <span className="shrink-0 tabular-nums text-muted-foreground/80">{testedRelative}</span>
      ) : null}
    </p>
  )

  const capabilityBadges = isPersonal ? (
    <PersonalTypeBadges types={item.modelTypes} selectorCapabilities={item.selectorCapabilities} />
  ) : isGatewayModelSource(item.source) ? (
    <ModelCapabilityBadges model={item.source} compact />
  ) : null

  const isRouteAlias = !!item.routeVirtualModel

  const titleLine = (
    <div className="flex min-w-0 items-center gap-2">
      {isRouteAlias ? (
        <span className="shrink-0 rounded bg-muted px-1 py-0.5 text-[10px] text-muted-foreground">
          别名
        </span>
      ) : null}
      <p
        className={cn(
          'min-w-0 flex-1 truncate',
          isPersonal ? 'text-sm font-medium' : 'font-mono text-sm font-medium',
          isRouteAlias && 'text-muted-foreground'
        )}
      >
        {item.title}
      </p>
      {isPersonal ? statusBadge : null}
    </div>
  )

  const stackedRowContent = (
    <>
      {titleLine}
      {personalMetaLines}
      {failShort ? <p className="mt-1 text-xs text-destructive">{failShort}</p> : null}
      {usageLoading ? (
        <p className="mt-1 text-xs text-muted-foreground">用量…</p>
      ) : usageText ? (
        <p className="mt-1 text-xs tabular-nums text-muted-foreground">{usageText}</p>
      ) : null}
      <div className="mt-1.5">{capabilityBadges}</div>
      {!item.enabled ? (
        <p className="mt-1 text-xs text-amber-600 dark:text-amber-400">已禁用</p>
      ) : null}
      {showSystemAdmin && isGatewayModelSource(item.source) ? (
        <SystemModelAdminMeta
          model={item.source}
          canDelete={rowCanDelete}
          configManaged={configManaged}
          isDeleting={isDeleting}
          onDelete={
            onDelete
              ? () => {
                  onDelete(item.id)
                }
              : undefined
          }
        />
      ) : null}
    </>
  )

  const compactRowContent = (
    <div className="min-w-0 space-y-1.5">
      {titleLine}
      {personalMetaLines}
      {failShort ? <p className="text-xs text-destructive">{failShort}</p> : null}
      {!item.enabled ? (
        <p className="text-xs font-medium text-amber-600 dark:text-amber-400">已禁用</p>
      ) : null}
      {usageLoading ? (
        <p className="text-xs text-muted-foreground">用量…</p>
      ) : usageText ? (
        <p className="text-xs tabular-nums text-muted-foreground">{usageText}</p>
      ) : null}
      {capabilityBadges}
      {showSystemAdmin && isGatewayModelSource(item.source) ? (
        <SystemModelAdminMeta
          model={item.source}
          canDelete={rowCanDelete}
          configManaged={configManaged}
          isDeleting={isDeleting}
          onDelete={
            onDelete
              ? () => {
                  onDelete(item.id)
                }
              : undefined
          }
        />
      ) : null}
    </div>
  )

  const rowContent = isCompact ? compactRowContent : stackedRowContent

  const hasTrailing = trailingActions !== null && trailingActions !== undefined
  const navigable =
    !isColumns &&
    capabilities.rowNavigation !== false &&
    (href !== undefined || onSelect !== undefined)
  const mainRowClassName = cn(rowClassName, 'min-w-0 overflow-hidden', hasTrailing && 'block')

  const mainRow =
    href && navigable ? (
      <Link
        to={href}
        className={mainRowClassName}
        onMouseEnter={onPreloadNavigate}
        onFocus={onPreloadNavigate}
      >
        {rowContent}
      </Link>
    ) : navigable ? (
      <button
        type="button"
        onClick={() => {
          onSelect?.(item.id)
        }}
        className={mainRowClassName}
      >
        {rowContent}
      </button>
    ) : (
      <div className={mainRowClassName}>{rowContent}</div>
    )

  const batchSelectCell = batchSelectEnabled ? (
    <div
      className={cn(
        'flex shrink-0 items-center justify-center px-2',
        isColumns ? 'py-2.5' : !isCompact && 'items-start pt-3'
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
          aria-label={`选择模型 ${item.title}`}
          onCheckedChange={(checked) => {
            onBatchSelectChange?.(item.id, checked === true)
          }}
        />
      ) : (
        <TooltipProvider delayDuration={300}>
          <Tooltip>
            <TooltipTrigger asChild>
              <span tabIndex={0}>
                <Checkbox checked={false} disabled aria-label={`不可选择 ${item.title}`} />
              </span>
            </TooltipTrigger>
            <TooltipContent className="max-w-xs text-xs">
              {configManaged ? CONFIG_MANAGED_BATCH_HINT : '无删除权限'}
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      )}
    </div>
  ) : null

  const trailingCell = hasTrailing ? (
    <div
      className={cn(
        'flex shrink-0 items-center justify-end gap-1 px-2.5 py-2',
        isColumns
          ? 'min-w-0 border-0 bg-transparent px-3 py-2.5'
          : 'border-l border-border/50 bg-card/80',
        !isColumns &&
          'sticky right-0 z-[1] shadow-[-10px_0_12px_-10px_hsl(var(--background)/0.9)] group-hover:bg-muted/30 sm:px-3'
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
      {isColumns ? null : !isPersonal ? statusBadge : null}
      {trailingActions}
    </div>
  ) : !isColumns && !isPersonal && statusBadge ? (
    <div className="flex shrink-0 items-center px-3 py-2">{statusBadge}</div>
  ) : null

  const affiliationCell =
    showAffiliationColumn && teamNameById ? (
      <div
        className={cn(
          'min-w-0 px-3 py-2.5',
          !isColumns && 'flex shrink-0 items-center',
          !isCompact && !isColumns && 'items-start pt-3'
        )}
      >
        <ModelAffiliationCell
          scope={item.scope}
          teamId={item.teamId}
          teamNameById={teamNameById}
          plain={isColumns}
        />
      </div>
    ) : null

  if (isColumns) {
    const invokeName = clientInvokeModelName(item)
    const displayName = listDisplayName(item)
    const channel = upstreamChannelLabel(item)
    const capabilityText = listCapabilityLabel(item)
    const capabilityFullText = listCapabilityFullLabel(item)
    const credentialName = listCredentialName(item)
    const contextWindowLabel = listContextWindowLabel(item)
    const contextWindowTokens = resolveContextWindow(item.selectorCapabilities)

    return (
      <li
        data-connectivity-model-id={item.id}
        className={cn(
          'group/row border-b border-border/40 transition-colors last:border-b-0 hover:bg-muted/30',
          highlighted && 'bg-primary/5',
          selected && 'bg-primary/10'
        )}
      >
        <div
          className="grid w-full min-w-0 items-center"
          style={
            columnsGrid
              ? {
                  gridTemplateColumns: columnsGrid.gridTemplateColumns,
                  minWidth: columnsGrid.tableMinWidth,
                }
              : undefined
          }
        >
          {batchSelectCell}
          {affiliationCell}
          <div className="min-w-0 px-3 py-2.5">
            <div className="flex min-w-0 items-center gap-1.5">
              {item.routeVirtualModel ? (
                <span className="shrink-0 rounded border border-border/60 bg-muted/50 px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
                  别名
                </span>
              ) : null}
              <CopyableText
                value={invokeName}
                emphasis
                ariaLabel={`复制调用名 ${invokeName}`}
                className="min-w-0 flex-1"
              />
            </div>
          </div>
          <div className="min-w-0 px-3 py-2.5">
            {displayName ? (
              <CopyableText
                value={displayName}
                mono={false}
                ariaLabel={`复制显示名 ${displayName}`}
              />
            ) : (
              <span className="px-1 text-sm text-muted-foreground/70">—</span>
            )}
          </div>
          <div className="min-w-0 px-3 py-2.5">
            <ListCellText value={channel} />
          </div>
          <div className="min-w-0 px-3 py-2.5">
            <CopyableText
              value={item.upstreamModelId}
              ariaLabel={`复制上游模型 ${item.upstreamModelId}`}
            />
          </div>
          <div className="min-w-0 px-3 py-2.5">
            {contextWindowTokens > 0 ? (
              <TooltipProvider delayDuration={200}>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <span className="text-sm tabular-nums">{contextWindowLabel}</span>
                  </TooltipTrigger>
                  <TooltipContent className="text-xs tabular-nums">
                    {String(contextWindowTokens)} tokens
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            ) : (
              <span className="text-sm text-muted-foreground/70">—</span>
            )}
          </div>
          <div className="min-w-0 px-3 py-2.5">
            <ListCellText value={capabilityText} tooltip={capabilityFullText} />
          </div>
          <div className="min-w-0 px-3 py-2.5">
            {credentialName ? (
              <ListCellText value={credentialName} />
            ) : (
              <span className="text-sm text-muted-foreground/70">—</span>
            )}
          </div>
          <div className="px-3 py-2.5">
            <div className="flex min-w-0 flex-col gap-1">
              <ModelStatusBadge
                status={item.lastTestStatus}
                testedAt={item.lastTestedAt}
                reason={item.lastTestReason}
                compact
                withProvider={false}
              />
              {failShort ? (
                <ListCellText value={failShort} className="text-[10px] text-destructive" />
              ) : null}
              {!item.enabled ? (
                <span className="text-[10px] font-medium text-amber-600 dark:text-amber-400">
                  已禁用
                </span>
              ) : null}
            </div>
          </div>
          {trailingCell}
        </div>
      </li>
    )
  }

  const rowGridClassName = cn(
    'grid w-full min-w-0 items-stretch',
    batchSelectEnabled &&
      showAffiliationColumn &&
      hasTrailing &&
      'grid-cols-[auto_96px_minmax(0,1fr)_auto]',
    batchSelectEnabled &&
      showAffiliationColumn &&
      !hasTrailing &&
      'grid-cols-[auto_96px_minmax(0,1fr)]',
    batchSelectEnabled &&
      !showAffiliationColumn &&
      hasTrailing &&
      'grid-cols-[auto_minmax(0,1fr)_auto]',
    batchSelectEnabled &&
      !showAffiliationColumn &&
      !hasTrailing &&
      'grid-cols-[auto_minmax(0,1fr)]',
    !batchSelectEnabled &&
      showAffiliationColumn &&
      hasTrailing &&
      'grid-cols-[96px_minmax(0,1fr)_auto]',
    !batchSelectEnabled &&
      showAffiliationColumn &&
      !hasTrailing &&
      'grid-cols-[96px_minmax(0,1fr)]',
    !batchSelectEnabled &&
      !showAffiliationColumn &&
      hasTrailing &&
      'grid-cols-[minmax(0,1fr)_auto]',
    !batchSelectEnabled && !showAffiliationColumn && !hasTrailing && 'grid-cols-[minmax(0,1fr)]'
  )

  return (
    <li
      data-connectivity-model-id={item.id}
      className={cn(
        'group',
        !hasTrailing && '[contain-intrinsic-size:auto_2.75rem] [content-visibility:auto]'
      )}
    >
      <div className={rowGridClassName}>
        {batchSelectCell}
        {affiliationCell}
        {mainRow}
        {trailingCell}
      </div>
    </li>
  )
})
