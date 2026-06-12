/**
 * 协作团队 + 模型分组列表（统一 ViewModel 版）。
 */

import { useCallback, useState } from 'react'
import type React from 'react'

import { Link } from 'react-router-dom'

import type { GatewayModel } from '@/api/gateway/models'
import { ConfirmAlertDialog } from '@/components/confirm-alert-dialog'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import {
  canDeleteGatewayModel,
  canManageGatewayModel,
} from '@/features/gateway-models/gateway-model-permissions'
import { formatSingleGatewayModelDeleteDescription } from '@/features/gateway-models/model-delete-copy'
import { teamModelsRegisterHref } from '@/features/gateway-models/paths'
import { CollaborationTeamGroupHeader } from '@/features/gateway-teams/collaboration-team-group-header'
import { isGatewayTeamWritable } from '@/features/gateway-teams/gateway-team-write-policy'
import { Loader2, Plus, Search, Trash2 } from '@/lib/lucide-icons'

import { GatewayModelListRow } from './gateway-model-list-row'
import { buildManagedTeamRouteUsageKey } from './usage-keys'

import type { GatewayModelGroupedListProps, GatewayModelListItem } from './types'

function asGatewayModel(item: GatewayModelListItem): GatewayModel {
  return item.source as GatewayModel
}

export function GatewayModelGroupedList({
  capabilities,
  teams,
  itemsByTeamId,
  tenantIdsWithModels,
  requiresSearch,
  isLoading,
  currentPage,
  isPlatformAdmin,
  canContribute = false,
  viewerUserId,
  updatePendingModelId,
  deletingModelId,
  getModelHref,
  onPreloadNavigate,
  onToggleEnabled,
  onDelete,
  renderTrailingActions,
  canManage,
  canDelete,
  canBatchSelect,
  isConfigManaged,
  selectedIds,
  onBatchSelectChange,
  highlightModelId,
  usageDays = 7,
  usageByRouteName,
  usageLoading = false,
}: GatewayModelGroupedListProps): React.JSX.Element {
  const [pendingDelete, setPendingDelete] = useState<{
    item: GatewayModelListItem
    teamId: string
  } | null>(null)

  const handleConfirmDelete = useCallback(() => {
    if (!pendingDelete) return
    onDelete(pendingDelete.item, pendingDelete.teamId)
    setPendingDelete(null)
  }, [onDelete, pendingDelete])

  if (requiresSearch) {
    return (
      <div className="px-4 py-10 text-center">
        <Search className="mx-auto h-8 w-8 text-muted-foreground/60" aria-hidden />
        <h3 className="mt-3 text-base font-semibold">团队数量较多</h3>
        <p className="mt-1 text-sm text-muted-foreground">
          请使用上方搜索框按团队名称筛选，再为对应团队添加模型。
        </p>
      </div>
    )
  }

  if (isLoading && teams.length === 0) {
    return <div className="px-4 py-12 text-center text-sm text-muted-foreground">加载中…</div>
  }

  const defaultTrailing = (
    item: GatewayModelListItem,
    teamId: string,
    ctx: { canManage: boolean; canDelete: boolean; isUpdating: boolean; isDeleting: boolean }
  ): React.ReactNode => {
    if (!ctx.canManage || capabilities.rowToggleEnabled === false) return null
    return (
      <div className="flex items-center gap-2">
        <Tooltip>
          <TooltipTrigger asChild>
            <div className="flex items-center gap-1.5">
              <span className="hidden text-xs text-muted-foreground lg:inline">
                {item.enabled ? '已启用' : '已禁用'}
              </span>
              <Switch
                checked={item.enabled}
                disabled={ctx.isUpdating || ctx.isDeleting}
                aria-label={`${item.enabled ? '禁用' : '启用'} ${item.title}`}
                onCheckedChange={(checked) => {
                  onToggleEnabled(item, teamId, checked)
                }}
              />
            </div>
          </TooltipTrigger>
          <TooltipContent side="left" className="text-xs lg:hidden">
            {item.enabled ? '点击禁用模型' : '点击启用模型'}
          </TooltipContent>
        </Tooltip>
        {ctx.canDelete && capabilities.rowDelete !== false ? (
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                type="button"
                size="icon"
                variant="ghost"
                className="h-8 w-8 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                disabled={ctx.isDeleting || ctx.isUpdating}
                aria-label={`删除 ${item.title}`}
                onClick={() => {
                  setPendingDelete({ item, teamId })
                }}
              >
                {ctx.isDeleting ? (
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
  }

  const resolveTrailing = renderTrailingActions ?? defaultTrailing

  return (
    <>
      <TooltipProvider delayDuration={300}>
        <div className="divide-y">
          {teams.map((team) => {
            const teamItems = itemsByTeamId.get(team.id) ?? []
            const hasModelsOnServer = tenantIdsWithModels.has(team.id)
            const showOffPageHint = hasModelsOnServer && teamItems.length === 0 && currentPage > 1
            const teamCanWrite = isGatewayTeamWritable(team, isPlatformAdmin)
            // 成员可在自己的凭据下注册模型；注册表单仍只列出本人可绑定的凭据。
            const teamCanRegister = teamCanWrite || canContribute

            return (
              <section key={team.id} aria-label={`团队 ${team.name} 模型`}>
                <CollaborationTeamGroupHeader
                  team={team}
                  isPlatformAdmin={isPlatformAdmin}
                  viewerUserId={viewerUserId}
                  actions={
                    teamCanRegister ? (
                      <Button size="sm" className="h-7 text-xs" asChild>
                        <Link to={teamModelsRegisterHref(team.id)}>
                          <Plus className="mr-1 h-3.5 w-3.5" />
                          添加模型
                        </Link>
                      </Button>
                    ) : null
                  }
                />
                {teamItems.length > 0 ? (
                  <ul className="divide-y">
                    {teamItems.map((item) => {
                      const model = asGatewayModel(item)
                      const resolvedCanManage =
                        canManage?.(item) ??
                        canManageGatewayModel(model, viewerUserId, teamCanWrite, isPlatformAdmin)
                      const resolvedCanDelete =
                        canDelete?.(item) ??
                        canDeleteGatewayModel(model, viewerUserId, teamCanWrite, isPlatformAdmin)
                      const resolvedCanBatchSelect = canBatchSelect?.(item) ?? resolvedCanDelete
                      const isUpdating = updatePendingModelId === item.id
                      const isDeleting = deletingModelId === item.id

                      return (
                        <GatewayModelListRow
                          key={`${item.id}:${team.id}`}
                          item={item}
                          capabilities={capabilities}
                          href={getModelHref(team.id, item.id)}
                          onPreloadNavigate={onPreloadNavigate}
                          highlighted={
                            highlightModelId !== undefined && item.id === highlightModelId
                          }
                          usageDays={usageDays}
                          usageRow={usageByRouteName?.get(
                            buildManagedTeamRouteUsageKey(team.id, item.title)
                          )}
                          usageLoading={usageLoading}
                          batchSelected={selectedIds?.has(item.id) ?? false}
                          onBatchSelectChange={onBatchSelectChange}
                          canBatchSelect={(i) => canBatchSelect?.(i) ?? resolvedCanBatchSelect}
                          canDelete={(i) => canDelete?.(i) ?? resolvedCanDelete}
                          isConfigManaged={isConfigManaged}
                          trailingActions={resolveTrailing(item, team.id, {
                            canManage: resolvedCanManage,
                            canDelete: resolvedCanDelete,
                            isUpdating,
                            isDeleting,
                          })}
                        />
                      )
                    })}
                  </ul>
                ) : showOffPageHint ? (
                  <p className="px-4 py-3 text-sm text-muted-foreground">
                    该团队已有模型，请翻页查看。
                  </p>
                ) : hasModelsOnServer && teamItems.length === 0 ? (
                  <p className="px-4 py-3 text-sm text-muted-foreground">
                    该团队已有模型（见其它页或未匹配当前筛选）。
                  </p>
                ) : (
                  <p className="px-4 py-3 text-sm text-muted-foreground">暂无模型</p>
                )}
              </section>
            )
          })}
          {teams.length === 0 ? (
            <div className="px-4 py-8 text-center text-sm text-muted-foreground">
              没有匹配的团队
            </div>
          ) : null}
        </div>
      </TooltipProvider>

      <ConfirmAlertDialog
        open={pendingDelete !== null}
        onOpenChange={(open) => {
          if (!open) setPendingDelete(null)
        }}
        title="删除团队模型"
        description={
          pendingDelete
            ? formatSingleGatewayModelDeleteDescription(pendingDelete.item.title, 'team')
            : '确定删除该模型？'
        }
        confirmLabel="确认删除"
        pending={deletingModelId !== null}
        onConfirm={handleConfirmDelete}
      />
    </>
  )
}
