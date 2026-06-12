/**
 * 统一模型列表（列布局 + 行内操作 + 详情入口）。
 */

import type React from 'react'

import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { GatewayModelAffiliatedFlatList } from '@/features/gateway-models/list/gateway-model-affiliated-flat-list'
import type {
  GatewayModelListCapabilities,
  GatewayModelListItem,
  GatewayModelListRowPermissions,
} from '@/features/gateway-models/list/types'
import { ChevronRight, Loader2, Trash2 } from '@/lib/lucide-icons'

export interface UnifiedModelsListProps extends GatewayModelListRowPermissions {
  items: readonly GatewayModelListItem[]
  capabilities: GatewayModelListCapabilities
  teamNameById: Map<string, string>
  highlightModelId?: string
  getItemHref: (item: GatewayModelListItem) => string | undefined
  onPreloadItemNavigate?: (item: GatewayModelListItem) => void
  deletingModelId?: string | null
  updatePendingModelId?: string | null
  onToggleEnabled?: (item: GatewayModelListItem, enabled: boolean) => void
  onRequestDelete?: (item: GatewayModelListItem) => void
  selectedIds?: ReadonlySet<string>
  onToggleSelect?: (id: string, selected: boolean) => void
  showAffiliationColumn?: boolean
}

export function UnifiedModelsList({
  items,
  capabilities,
  teamNameById,
  highlightModelId,
  getItemHref,
  onPreloadItemNavigate,
  canManage,
  canDelete,
  isConfigManaged,
  deletingModelId = null,
  updatePendingModelId = null,
  onToggleEnabled,
  onRequestDelete,
  selectedIds,
  onToggleSelect,
  canBatchSelect,
  showAffiliationColumn = true,
}: UnifiedModelsListProps): React.JSX.Element {
  if (items.length === 0) {
    return <p className="px-4 py-10 text-center text-sm text-muted-foreground">无匹配模型</p>
  }

  return (
    <GatewayModelAffiliatedFlatList
      capabilities={capabilities}
      items={items}
      teamNameById={teamNameById}
      showAffiliationColumn={showAffiliationColumn}
      highlightModelId={highlightModelId}
      getItemHref={getItemHref}
      onPreloadItemNavigate={onPreloadItemNavigate}
      canManage={canManage}
      canDelete={canDelete}
      canBatchSelect={canBatchSelect}
      isConfigManaged={isConfigManaged}
      deletingModelId={deletingModelId}
      selectedIds={selectedIds}
      onToggleSelect={onToggleSelect}
      renderTrailingActions={(item, ctx) => {
        const href = getItemHref(item)
        const manageable = canManage?.(item) ?? false
        const deletable = canDelete?.(item) ?? false
        const isUpdating = updatePendingModelId === item.id
        const isDeleting = ctx.isDeleting

        const hasRowActions =
          manageable ||
          deletable ||
          capabilities.rowToggleEnabled !== false ||
          capabilities.rowDelete !== false

        if (!href && !hasRowActions) return null

        return (
          <div className="flex items-center gap-1">
            {href ? (
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 text-muted-foreground"
                    asChild
                  >
                    <Link
                      to={href}
                      aria-label={`查看 ${item.title} 详情`}
                      onMouseEnter={() => {
                        onPreloadItemNavigate?.(item)
                      }}
                      onFocus={() => {
                        onPreloadItemNavigate?.(item)
                      }}
                    >
                      <ChevronRight className="h-4 w-4" />
                    </Link>
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="left" className="text-xs">
                  查看详情
                </TooltipContent>
              </Tooltip>
            ) : null}
            {manageable && capabilities.rowToggleEnabled !== false ? (
              <Tooltip>
                <TooltipTrigger asChild>
                  <div className="flex items-center gap-1">
                    <Switch
                      checked={item.enabled}
                      disabled={isUpdating || isDeleting}
                      aria-label={`${item.enabled ? '禁用' : '启用'} ${item.title}`}
                      onCheckedChange={(checked) => {
                        onToggleEnabled?.(item, checked)
                      }}
                    />
                  </div>
                </TooltipTrigger>
                <TooltipContent side="left" className="text-xs">
                  {item.enabled ? '已启用，点击禁用' : '已禁用，点击启用'}
                </TooltipContent>
              </Tooltip>
            ) : null}
            {deletable && capabilities.rowDelete !== false ? (
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    type="button"
                    size="icon"
                    variant="ghost"
                    className="h-8 w-8 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                    disabled={isDeleting || isUpdating}
                    aria-label={`删除 ${item.title}`}
                    onClick={() => {
                      onRequestDelete?.(item)
                    }}
                  >
                    {isDeleting ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Trash2 className="h-4 w-4" />
                    )}
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="left" className="text-xs">
                  删除模型
                </TooltipContent>
              </Tooltip>
            ) : null}
          </div>
        )
      }}
    />
  )
}
