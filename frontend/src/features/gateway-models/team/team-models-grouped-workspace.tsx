/**
 * 团队 Tab：按协作团队分组的模型列表（跨团队聚合）。
 */

import { useCallback, useDeferredValue, useMemo, useState } from 'react'
import type React from 'react'

import { Link } from 'react-router-dom'

import type { GatewayModel } from '@/api/gateway'
import { PaginationControls } from '@/components/pagination-controls'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useGatewayModelMutations } from '@/features/gateway-models/hooks/use-gateway-model-mutations'
import { teamModelsRegisterHref } from '@/features/gateway-models/paths'
import { CollaborationTeamsModelsGroupedList } from '@/features/gateway-models/team/collaboration-teams-models-grouped-list'
import { useManagedTeamModelsList } from '@/features/gateway-models/use-managed-team-models-list'
import { GatewayRefreshButton } from '@/features/gateway-shared/gateway-refresh-button'
import {
  groupModelsByTenantId,
  useCollaborationTeamsOverviewResolution,
} from '@/features/gateway-teams/use-collaboration-teams-overview-resolution'
import { useGatewayWritableCollaborationTeams } from '@/features/gateway-teams/use-gateway-teams'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { Plus, Search } from '@/lib/lucide-icons'
import { useUserStore } from '@/stores/user'

type ConnectivityFilter = 'all' | 'success' | 'failed' | 'unknown'

export function TeamModelsGroupedWorkspace(): React.JSX.Element {
  const writableCollaborationTeams = useGatewayWritableCollaborationTeams()
  const viewerUserId = useUserStore((s) => s.currentUser?.id ?? null)
  const { canWrite, isPlatformAdmin } = useGatewayPermission()

  const [teamSearch, setTeamSearch] = useState('')
  const deferredTeamSearch = useDeferredValue(teamSearch)
  const [modelSearch, setModelSearch] = useState('')
  const deferredModelSearch = useDeferredValue(modelSearch)
  const [connectivity, setConnectivity] = useState<ConnectivityFilter>('all')
  const [page, setPage] = useState(1)
  const [updatePendingModelId, setUpdatePendingModelId] = useState<string | null>(null)
  const [deletingModelId, setDeletingModelId] = useState<string | null>(null)

  const hasCollaborationTeams = writableCollaborationTeams.length > 0
  const teamSearchTrimmed = teamSearch.trim()
  const isListSearchStale = deferredTeamSearch.trim() !== teamSearchTrimmed

  const {
    data: listData,
    isLoading,
    isFetching,
    refetch,
  } = useManagedTeamModelsList({
    enabled: hasCollaborationTeams,
    search: deferredTeamSearch,
    page,
    q: deferredModelSearch,
    connectivity: connectivity === 'all' ? undefined : connectivity,
  })

  const { updateModelMutation, deleteModelMutation } = useGatewayModelMutations()

  const {
    teams: displayTeams,
    requiresSearch,
    isSearchStale: isTeamsSearchStale,
  } = useCollaborationTeamsOverviewResolution({
    teamSearch,
    queriedTeamCount: listData?.queried_team_count,
    isPlatformAdmin,
    viewerUserId,
    enabled: hasCollaborationTeams,
  })

  const modelsByTeamId = useMemo(
    () => groupModelsByTenantId(listData?.items ?? []),
    [listData?.items]
  )

  const tenantIdsWithModels = useMemo(
    () => new Set(listData?.tenant_ids_with_models ?? []),
    [listData?.tenant_ids_with_models]
  )

  const defaultRegisterTeamId = displayTeams[0]?.id ?? writableCollaborationTeams[0]?.id

  const handleTeamSearchChange = useCallback((value: string) => {
    setTeamSearch(value)
    setPage(1)
  }, [])

  const handleModelSearchChange = useCallback((value: string) => {
    setModelSearch(value)
    setPage(1)
  }, [])

  const handleToggleEnabled = useCallback(
    (model: GatewayModel, teamId: string, enabled: boolean) => {
      setUpdatePendingModelId(model.id)
      updateModelMutation.mutate(
        { id: model.id, body: { enabled }, teamId },
        {
          onSettled: () => {
            setUpdatePendingModelId(null)
          },
        }
      )
    },
    [updateModelMutation]
  )

  const handleDelete = useCallback(
    (model: GatewayModel, teamId: string) => {
      setDeletingModelId(model.id)
      deleteModelMutation.mutate(
        { id: model.id, teamId },
        {
          onSettled: () => {
            setDeletingModelId(null)
          },
        }
      )
    },
    [deleteModelMutation]
  )

  const showLoading = isLoading || isListSearchStale || isTeamsSearchStale
  const summaryLabel =
    listData !== undefined
      ? isPlatformAdmin
        ? `${String(listData.queried_shared_team_count)} 协作团队 · ${String(listData.total)} 模型`
        : `${String(listData.queried_team_count)} 团队 · ${String(listData.total)} 模型`
      : null

  const tableFooter =
    listData && listData.total > listData.page_size ? (
      <PaginationControls
        page={listData.page}
        page_size={listData.page_size}
        total={listData.total}
        has_next={listData.has_next}
        has_prev={listData.has_prev}
        onPageChange={setPage}
      />
    ) : null

  if (!hasCollaborationTeams) {
    return (
      <Card>
        <CardContent className="p-6 text-center text-sm text-muted-foreground">
          尚无协作团队。加入协作团队并获得管理员权限后，可在此注册团队模型。
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <div className="flex flex-wrap items-center gap-2 border-b p-3 sm:gap-3">
        {summaryLabel ? (
          <Badge variant="secondary" className="font-normal">
            {summaryLabel}
          </Badge>
        ) : null}
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <div className="relative min-w-[180px] max-w-xs">
            <Search className="pointer-events-none absolute left-2.5 top-2 h-4 w-4 text-muted-foreground" />
            <Input
              value={teamSearch}
              onChange={(e) => {
                handleTeamSearchChange(e.target.value)
              }}
              placeholder="按团队筛选"
              className="h-8 pl-8 text-sm"
              aria-label="按团队名称筛选"
            />
          </div>
          <Input
            value={modelSearch}
            onChange={(e) => {
              handleModelSearchChange(e.target.value)
            }}
            placeholder="按模型名筛选"
            className="h-8 w-[160px] text-sm"
            aria-label="按模型名称筛选"
          />
          <Select
            value={connectivity}
            onValueChange={(v) => {
              setConnectivity(v as ConnectivityFilter)
              setPage(1)
            }}
          >
            <SelectTrigger className="h-8 w-[120px] text-xs">
              <SelectValue placeholder="连通性" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部</SelectItem>
              <SelectItem value="success">可用</SelectItem>
              <SelectItem value="failed">失败</SelectItem>
              <SelectItem value="unknown">未测</SelectItem>
            </SelectContent>
          </Select>
          <GatewayRefreshButton
            isFetching={isFetching}
            ariaLabel="刷新团队模型"
            onRefresh={() => refetch()}
          />
          {canWrite ? (
            <Button size="sm" asChild>
              <Link to={teamModelsRegisterHref(defaultRegisterTeamId)}>
                <Plus className="mr-1.5 h-4 w-4" />
                添加模型
              </Link>
            </Button>
          ) : null}
        </div>
      </div>
      <CardContent className="p-0">
        <CollaborationTeamsModelsGroupedList
          teams={displayTeams}
          modelsByTeamId={modelsByTeamId}
          tenantIdsWithModels={tenantIdsWithModels}
          requiresSearch={requiresSearch}
          isLoading={showLoading}
          currentPage={page}
          canWrite={canWrite}
          isPlatformAdmin={isPlatformAdmin}
          viewerUserId={viewerUserId}
          updatePendingModelId={updatePendingModelId}
          deletingModelId={deletingModelId}
          onToggleEnabled={handleToggleEnabled}
          onDelete={handleDelete}
        />
      </CardContent>
      {tableFooter ? <div className="border-t px-3 py-2">{tableFooter}</div> : null}
    </Card>
  )
}
