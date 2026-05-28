import { memo, type ReactNode } from 'react'

import type { GatewayModelRouteUsageItem } from '@/api/gateway/models'
import { Checkbox } from '@/components/ui/checkbox'
import type { UsagePeriodDays } from '@/features/gateway-models/constants'

import { GatewayModelListRow } from './gateway-model-list-row'
import { buildRouteUsageKey } from './usage-keys'

import type {
  GatewayModelListCapabilities,
  GatewayModelListItem,
  GatewayModelListRowPermissions,
} from './types'

export interface GatewayModelFlatListProps extends GatewayModelListRowPermissions {
  capabilities: GatewayModelListCapabilities
  items: readonly GatewayModelListItem[]
  selectedIds?: ReadonlySet<string>
  onToggleSelect?: (id: string, selected: boolean) => void
  onToggleSelectAll?: (selected: boolean) => void
  selectableCount?: number
  allSelectableSelected?: boolean
  someSelectableSelected?: boolean
  highlightModelId?: string
  usageDays?: UsagePeriodDays
  usageByRouteName?: ReadonlyMap<string, GatewayModelRouteUsageItem>
  usageLoading?: boolean
  getItemHref?: (item: GatewayModelListItem) => string | undefined
  onPreloadNavigate?: () => void
  deletingModelId?: string | null
  onDelete?: (id: string) => void
  renderTrailingActions?: (item: GatewayModelListItem, ctx: { isDeleting: boolean }) => ReactNode
}

export const GatewayModelFlatList = memo(function GatewayModelFlatList({
  capabilities,
  items,
  selectedIds,
  onToggleSelect,
  onToggleSelectAll,
  selectableCount = 0,
  allSelectableSelected = false,
  someSelectableSelected = false,
  highlightModelId,
  usageDays = 7,
  usageByRouteName,
  usageLoading = false,
  getItemHref,
  onPreloadNavigate,
  deletingModelId = null,
  onDelete,
  renderTrailingActions,
  canManage,
  canDelete,
  canBatchSelect,
  isConfigManaged,
}: GatewayModelFlatListProps): React.JSX.Element {
  const batchSelectEnabled = capabilities.batchSelect === true

  return (
    <ul className="divide-y">
      {batchSelectEnabled && items.length > 0 ? (
        <li className="flex items-center gap-2 border-b bg-muted/20 px-3 py-2">
          <Checkbox
            checked={
              allSelectableSelected ? true : someSelectableSelected ? 'indeterminate' : false
            }
            disabled={selectableCount === 0}
            aria-label="全选可删除的模型"
            onCheckedChange={(checked) => {
              onToggleSelectAll?.(checked === true)
            }}
          />
          <span className="text-xs text-muted-foreground">
            全选可删除项{selectableCount > 0 ? `（${String(selectableCount)}）` : ''}
          </span>
        </li>
      ) : null}
      {items.map((item) => {
        const routeKey = buildRouteUsageKey(item.routeName ?? item.title)
        const isDeleting = deletingModelId === item.id
        return (
          <GatewayModelListRow
            key={item.id}
            item={item}
            capabilities={capabilities}
            highlighted={highlightModelId !== undefined && item.id === highlightModelId}
            usageDays={usageDays}
            usageRow={usageByRouteName?.get(routeKey)}
            usageLoading={usageLoading}
            href={getItemHref?.(item)}
            onPreloadNavigate={onPreloadNavigate}
            batchSelected={selectedIds?.has(item.id) ?? false}
            onBatchSelectChange={onToggleSelect}
            canManage={canManage}
            canDelete={canDelete}
            canBatchSelect={canBatchSelect}
            isConfigManaged={isConfigManaged}
            isDeleting={isDeleting}
            onDelete={onDelete}
            trailingActions={renderTrailingActions?.(item, { isDeleting })}
          />
        )
      })}
    </ul>
  )
})
