/**
 * 协作团队 + 模型分组列表。
 */

import { useCallback, useState } from 'react'
import type React from 'react'

import { Link } from 'react-router-dom'

import type { GatewayModel } from '@/api/gateway'
import type { GatewayTeam } from '@/api/gateway/teams'
import { ConfirmAlertDialog } from '@/components/confirm-alert-dialog'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Switch } from '@/components/ui/switch'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import {
  canDeleteGatewayModel,
  canManageGatewayModel,
} from '@/features/gateway-models/gateway-model-permissions'
import { teamModelDetailHref, teamModelsRegisterHref } from '@/features/gateway-models/paths'
import { ModelInventoryRow } from '@/features/gateway-models/team/model-inventory-row'
import { CollaborationTeamGroupHeader } from '@/features/gateway-teams/collaboration-team-group-header'
import { isGatewayTeamWritable } from '@/features/gateway-teams/gateway-team-write-policy'
import { Loader2, Plus, Search, Trash2 } from '@/lib/lucide-icons'

export interface CollaborationTeamsModelsGroupedListProps {
  teams: readonly GatewayTeam[]
  modelsByTeamId: ReadonlyMap<string, readonly GatewayModel[]>
  tenantIdsWithModels: ReadonlySet<string>
  requiresSearch: boolean
  isLoading: boolean
  currentPage: number
  isPlatformAdmin: boolean
  viewerUserId?: string | null
  updatePendingModelId?: string | null
  deletingModelId?: string | null
  onToggleEnabled: (model: GatewayModel, teamId: string, enabled: boolean) => void
  onDelete: (model: GatewayModel, teamId: string) => void
}

export function CollaborationTeamsModelsGroupedList({
  teams,
  modelsByTeamId,
  tenantIdsWithModels,
  requiresSearch,
  isLoading,
  currentPage,
  isPlatformAdmin,
  viewerUserId,
  updatePendingModelId,
  deletingModelId,
  onToggleEnabled,
  onDelete,
}: CollaborationTeamsModelsGroupedListProps): React.JSX.Element {
  const [pendingDelete, setPendingDelete] = useState<{
    model: GatewayModel
    teamId: string
  } | null>(null)

  const handleConfirmDelete = useCallback(() => {
    if (!pendingDelete) return
    onDelete(pendingDelete.model, pendingDelete.teamId)
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

  return (
    <>
      <TooltipProvider delayDuration={300}>
        <ScrollArea className="max-h-[min(70vh,720px)] w-full overscroll-y-contain">
          {/* pr-3：为 Radix 垂直滚动条预留 gutter，避免挡住行尾开关/删除 */}
          <div className="divide-y pr-3">
            {teams.map((team) => {
              const teamModels = modelsByTeamId.get(team.id) ?? []
              const hasModelsOnServer = tenantIdsWithModels.has(team.id)
              const showOffPageHint =
                hasModelsOnServer && teamModels.length === 0 && currentPage > 1
              const teamCanWrite = isGatewayTeamWritable(team, isPlatformAdmin)

              return (
                <section key={team.id} aria-label={`团队 ${team.name} 模型`}>
                  <CollaborationTeamGroupHeader
                    team={team}
                    isPlatformAdmin={isPlatformAdmin}
                    viewerUserId={viewerUserId}
                    actions={
                      teamCanWrite ? (
                        <Button size="sm" className="h-7 text-xs" asChild>
                          <Link to={teamModelsRegisterHref(team.id)}>
                            <Plus className="mr-1 h-3.5 w-3.5" />
                            添加模型
                          </Link>
                        </Button>
                      ) : null
                    }
                  />
                  {teamModels.length > 0 ? (
                    <ul className="divide-y">
                      {teamModels.map((model) => {
                        const canManage = canManageGatewayModel(
                          model,
                          viewerUserId,
                          teamCanWrite,
                          isPlatformAdmin
                        )
                        const canDelete = canDeleteGatewayModel(
                          model,
                          viewerUserId,
                          teamCanWrite,
                          isPlatformAdmin
                        )
                        const isUpdating = updatePendingModelId === model.id
                        const isDeleting = deletingModelId === model.id

                        return (
                          <ModelInventoryRow
                            key={`${model.id}:${team.id}`}
                            model={model}
                            selected={false}
                            highlighted={false}
                            usageDays={7}
                            usageRow={undefined}
                            usageLoading={false}
                            layout="compact"
                            connectivityDisplay="attention-only"
                            href={teamModelDetailHref(team.id, model.id)}
                            trailingActions={
                              canManage ? (
                                <div className="flex items-center gap-2">
                                  <Tooltip>
                                    <TooltipTrigger asChild>
                                      <div className="flex items-center gap-1.5">
                                        <span className="hidden text-xs text-muted-foreground lg:inline">
                                          {model.enabled ? '已启用' : '已禁用'}
                                        </span>
                                        <Switch
                                          checked={model.enabled}
                                          disabled={isUpdating || isDeleting}
                                          aria-label={`${model.enabled ? '禁用' : '启用'} ${model.name}`}
                                          onCheckedChange={(checked) => {
                                            onToggleEnabled(model, team.id, checked)
                                          }}
                                        />
                                      </div>
                                    </TooltipTrigger>
                                    <TooltipContent side="left" className="text-xs lg:hidden">
                                      {model.enabled ? '点击禁用模型' : '点击启用模型'}
                                    </TooltipContent>
                                  </Tooltip>
                                  {canDelete ? (
                                    <Tooltip>
                                      <TooltipTrigger asChild>
                                        <Button
                                          type="button"
                                          size="icon"
                                          variant="ghost"
                                          className="h-8 w-8 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                                          disabled={isDeleting || isUpdating}
                                          aria-label={`删除 ${model.name}`}
                                          onClick={() => {
                                            setPendingDelete({ model, teamId: team.id })
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
                              ) : null
                            }
                          />
                        )
                      })}
                    </ul>
                  ) : showOffPageHint ? (
                    <p className="px-4 py-3 text-sm text-muted-foreground">
                      该团队已有模型，请翻页查看。
                    </p>
                  ) : hasModelsOnServer && teamModels.length === 0 ? (
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
        </ScrollArea>
      </TooltipProvider>

      <ConfirmAlertDialog
        open={pendingDelete !== null}
        onOpenChange={(open) => {
          if (!open) setPendingDelete(null)
        }}
        title="删除团队模型"
        description={
          pendingDelete
            ? `确定删除模型「${pendingDelete.model.name}」？将同步更新虚拟 Key / 路由中的模型白名单，并清理相关授权与预算行。此操作不可撤销。`
            : '确定删除该模型？'
        }
        confirmLabel="确认删除"
        pending={deletingModelId !== null}
        onConfirm={handleConfirmDelete}
      />
    </>
  )
}
