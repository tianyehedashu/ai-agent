import { memo, type ReactNode } from 'react'

import type { GatewayModelRouteUsageItem } from '@/api/gateway/models'
import type { UsagePeriodDays } from '@/features/gateway-models/constants'

import { GatewayModelListHead } from './gateway-model-list-head'
import { GatewayModelListRow } from './gateway-model-list-row'
import {
  ModelListColumnsLayoutProvider,
  useModelListColumnsLayout,
} from './model-list-columns-layout'
import { buildManagedTeamRouteUsageKey, buildRouteUsageKey } from './usage-keys'

import type {
  GatewayModelListCapabilities,
  GatewayModelListItem,
  GatewayModelListRowPermissions,
} from './types'

export interface GatewayModelAffiliatedFlatListProps extends GatewayModelListRowPermissions {
  capabilities: GatewayModelListCapabilities
  items: readonly GatewayModelListItem[]
  teamNameById: Map<string, string>
  selectedIds?: ReadonlySet<string>
  onToggleSelect?: (id: string, selected: boolean) => void
  highlightModelId?: string
  usageDays?: UsagePeriodDays
  usageByRouteName?: ReadonlyMap<string, GatewayModelRouteUsageItem>
  usageLoading?: boolean
  getItemHref?: (item: GatewayModelListItem) => string | undefined
  onPreloadNavigate?: () => void
  onPreloadItemNavigate?: (item: GatewayModelListItem) => void
  deletingModelId?: string | null
  onDelete?: (id: string) => void
  renderTrailingActions?: (
    item: GatewayModelListItem,
    ctx: { isDeleting: boolean; teamId?: string | null }
  ) => ReactNode
  resolveUsageKey?: (item: GatewayModelListItem) => string
  showAffiliationColumn?: boolean
}

interface ColumnsModelListBodyProps extends Omit<
  GatewayModelAffiliatedFlatListProps,
  'capabilities' | 'items' | 'teamNameById'
> {
  capabilities: GatewayModelListCapabilities
  items: readonly GatewayModelListItem[]
  teamNameById: Map<string, string>
}

const ColumnsModelListBody = memo(function ColumnsModelListBody({
  capabilities,
  items,
  teamNameById,
  selectedIds,
  onToggleSelect,
  highlightModelId,
  usageDays = 7,
  usageByRouteName,
  usageLoading = false,
  getItemHref,
  onPreloadNavigate,
  onPreloadItemNavigate,
  deletingModelId = null,
  onDelete,
  renderTrailingActions,
  canManage,
  canDelete,
  canBatchSelect,
  isConfigManaged,
  resolveUsageKey,
  showAffiliationColumn = true,
}: ColumnsModelListBodyProps): React.JSX.Element {
  const { gridTemplateColumns, tableMinWidth } = useModelListColumnsLayout()
  const columnsGrid = { gridTemplateColumns, tableMinWidth }

  return (
    <ul>
      {items.map((item) => {
        const routeKey =
          resolveUsageKey?.(item) ??
          (item.scope === 'team' && item.teamId
            ? buildManagedTeamRouteUsageKey(item.teamId, item.title)
            : buildRouteUsageKey(item.routeName ?? item.title))
        const isDeleting = deletingModelId === item.id
        return (
          <GatewayModelListRow
            key={`${item.scope}:${item.id}`}
            item={item}
            capabilities={capabilities}
            showAffiliationColumn={showAffiliationColumn}
            teamNameById={teamNameById}
            highlighted={highlightModelId !== undefined && item.id === highlightModelId}
            usageDays={usageDays}
            usageRow={usageByRouteName?.get(routeKey)}
            usageLoading={usageLoading}
            href={getItemHref?.(item)}
            onPreloadNavigate={() => {
              onPreloadItemNavigate?.(item)
              onPreloadNavigate?.()
            }}
            batchSelected={selectedIds?.has(item.id) ?? false}
            onBatchSelectChange={onToggleSelect}
            canManage={canManage}
            canDelete={canDelete}
            canBatchSelect={canBatchSelect}
            isConfigManaged={isConfigManaged}
            isDeleting={isDeleting}
            onDelete={onDelete}
            columnsGrid={columnsGrid}
            trailingActions={renderTrailingActions?.(item, {
              isDeleting,
              teamId: item.teamId,
            })}
          />
        )
      })}
    </ul>
  )
})

export const GatewayModelAffiliatedFlatList = memo(function GatewayModelAffiliatedFlatList({
  capabilities,
  items,
  teamNameById,
  selectedIds,
  onToggleSelect,
  highlightModelId,
  usageDays = 7,
  usageByRouteName,
  usageLoading = false,
  getItemHref,
  onPreloadNavigate,
  onPreloadItemNavigate,
  deletingModelId = null,
  onDelete,
  renderTrailingActions,
  canManage,
  canDelete,
  canBatchSelect,
  isConfigManaged,
  resolveUsageKey,
  showAffiliationColumn = true,
}: GatewayModelAffiliatedFlatListProps): React.JSX.Element {
  const batchSelectEnabled = capabilities.batchSelect === true
  const listLayout = capabilities.layout ?? 'compact'
  const isColumnsLayout = listLayout === 'columns'
  const hasTrailing =
    capabilities.rowToggleEnabled !== false ||
    capabilities.rowDelete !== false ||
    renderTrailingActions !== undefined

  if (isColumnsLayout) {
    return (
      <ModelListColumnsLayoutProvider
        showBatchSelect={batchSelectEnabled}
        showTrailing={hasTrailing}
        showAffiliationColumn={showAffiliationColumn}
      >
        <div className="overflow-x-auto">
          <GatewayModelListHead
            showAffiliationColumn={showAffiliationColumn}
            showBatchSelect={batchSelectEnabled}
            showTrailing={hasTrailing}
            layout={listLayout}
          />
          <ColumnsModelListBody
            capabilities={capabilities}
            items={items}
            teamNameById={teamNameById}
            selectedIds={selectedIds}
            onToggleSelect={onToggleSelect}
            highlightModelId={highlightModelId}
            usageDays={usageDays}
            usageByRouteName={usageByRouteName}
            usageLoading={usageLoading}
            getItemHref={getItemHref}
            onPreloadNavigate={onPreloadNavigate}
            onPreloadItemNavigate={onPreloadItemNavigate}
            deletingModelId={deletingModelId}
            onDelete={onDelete}
            renderTrailingActions={renderTrailingActions}
            canManage={canManage}
            canDelete={canDelete}
            canBatchSelect={canBatchSelect}
            isConfigManaged={isConfigManaged}
            resolveUsageKey={resolveUsageKey}
            showAffiliationColumn={showAffiliationColumn}
          />
        </div>
      </ModelListColumnsLayoutProvider>
    )
  }

  return (
    <div>
      <GatewayModelListHead
        showAffiliationColumn
        showBatchSelect={batchSelectEnabled}
        showTrailing={hasTrailing}
        layout={listLayout}
      />
      <ul className="divide-y">
        {items.map((item) => {
          const routeKey =
            resolveUsageKey?.(item) ??
            (item.scope === 'team' && item.teamId
              ? buildManagedTeamRouteUsageKey(item.teamId, item.title)
              : buildRouteUsageKey(item.routeName ?? item.title))
          const isDeleting = deletingModelId === item.id
          return (
            <GatewayModelListRow
              key={`${item.scope}:${item.id}`}
              item={item}
              capabilities={capabilities}
              showAffiliationColumn
              teamNameById={teamNameById}
              highlighted={highlightModelId !== undefined && item.id === highlightModelId}
              usageDays={usageDays}
              usageRow={usageByRouteName?.get(routeKey)}
              usageLoading={usageLoading}
              href={getItemHref?.(item)}
              onPreloadNavigate={() => {
                onPreloadItemNavigate?.(item)
                onPreloadNavigate?.()
              }}
              batchSelected={selectedIds?.has(item.id) ?? false}
              onBatchSelectChange={onToggleSelect}
              canManage={canManage}
              canDelete={canDelete}
              canBatchSelect={canBatchSelect}
              isConfigManaged={isConfigManaged}
              isDeleting={isDeleting}
              onDelete={onDelete}
              trailingActions={renderTrailingActions?.(item, {
                isDeleting,
                teamId: item.teamId,
              })}
            />
          )
        })}
      </ul>
    </div>
  )
})
