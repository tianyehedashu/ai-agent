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
import { ConnectivityBatchTestBanner } from '@/features/gateway-models/connectivity-batch-test-banner'
import { ConnectivityHealthStrip } from '@/features/gateway-models/connectivity-health-strip'
import { FILTER_ALL, type HealthFilter } from '@/features/gateway-models/constants'
import {
  canDeleteGatewayModel,
  canManageGatewayModel,
  canResyncGatewayModelCapabilities,
} from '@/features/gateway-models/gateway-model-permissions'
import { useGatewayModelConnectivityBatchOps } from '@/features/gateway-models/hooks/use-gateway-model-connectivity-batch-ops'
import { useGatewayModelMutations } from '@/features/gateway-models/hooks/use-gateway-model-mutations'
import {
  ModelBatchDeleteConfirmDialog,
  ModelBatchDeleteFailedDialog,
} from '@/features/gateway-models/model-batch-delete-dialogs'
import { teamModelsRegisterHref } from '@/features/gateway-models/paths'
import { RegistryAbilityFilterSelect } from '@/features/gateway-models/registry-ability-filter-select'
import { CollaborationTeamsModelsGroupedList } from '@/features/gateway-models/team/collaboration-teams-models-grouped-list'
import { useManagedTeamModelsList } from '@/features/gateway-models/use-managed-team-models-list'
import { channelLabel, resolveGatewayModelTeamId } from '@/features/gateway-models/utils'
import { GatewayRefreshButton } from '@/features/gateway-shared/gateway-refresh-button'
import { isGatewayTeamWritable } from '@/features/gateway-teams/gateway-team-write-policy'
import {
  groupModelsByTenantId,
  useCollaborationTeamsOverviewResolution,
} from '@/features/gateway-teams/use-collaboration-teams-overview-resolution'
import {
  useGatewayMemberCollaborationTeams,
  useGatewayWritableCollaborationTeams,
} from '@/features/gateway-teams/use-gateway-teams'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { Plus, Search } from '@/lib/lucide-icons'
import { PROVIDER_CHANNEL_FILTER_HINT_GATEWAY } from '@/lib/provider-channel-hint'
import { useUserStore } from '@/stores/user'
import { MODEL_PROVIDERS } from '@/types/user-model'

export function TeamModelsGroupedWorkspace(): React.JSX.Element {
  const memberCollaborationTeams = useGatewayMemberCollaborationTeams()
  const writableCollaborationTeams = useGatewayWritableCollaborationTeams()
  const viewerUserId = useUserStore((s) => s.currentUser?.id ?? null)
  const { canWrite, isPlatformAdmin } = useGatewayPermission()

  const [teamSearch, setTeamSearch] = useState('')
  const deferredTeamSearch = useDeferredValue(teamSearch)
  const [modelSearch, setModelSearch] = useState('')
  const deferredModelSearch = useDeferredValue(modelSearch)
  const [healthFilter, setHealthFilter] = useState<HealthFilter>('all')
  const [providerFilter, setProviderFilter] = useState('')
  const [abilityFilter, setAbilityFilter] = useState('')
  const [page, setPage] = useState(1)
  const [updatePendingModelId, setUpdatePendingModelId] = useState<string | null>(null)
  const [deletingModelId, setDeletingModelId] = useState<string | null>(null)

  const hasCollaborationTeams = memberCollaborationTeams.length > 0
  const teamSearchTrimmed = teamSearch.trim()
  const isListSearchStale = deferredTeamSearch.trim() !== teamSearchTrimmed

  const listQueryBase = useMemo(
    () => ({
      ...(deferredTeamSearch.trim() ? { search: deferredTeamSearch.trim() } : {}),
      ...(deferredModelSearch.trim() ? { q: deferredModelSearch.trim() } : {}),
      ...(providerFilter ? { provider: providerFilter } : {}),
      ...(abilityFilter ? { type: abilityFilter } : {}),
    }),
    [deferredTeamSearch, deferredModelSearch, providerFilter, abilityFilter]
  )

  const {
    data: listData,
    isLoading,
    isFetching,
    refetch,
  } = useManagedTeamModelsList({
    enabled: hasCollaborationTeams,
    page,
    connectivity: healthFilter === 'all' ? undefined : healthFilter,
    ...listQueryBase,
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

  const registryItems = useMemo(() => listData?.items ?? [], [listData?.items])
  const connectivitySummary = listData?.connectivity_summary

  const teamWritableById = useMemo(() => {
    const map = new Map<string, boolean>()
    for (const team of displayTeams) {
      map.set(team.id, isGatewayTeamWritable(team, isPlatformAdmin))
    }
    return map
  }, [displayTeams, isPlatformAdmin])

  const resolveTeamCanWrite = useCallback(
    (model: GatewayModel): boolean => {
      const teamId = resolveGatewayModelTeamId(model)
      if (!teamId) return false
      return teamWritableById.get(teamId) ?? false
    },
    [teamWritableById]
  )

  const canManageModel = useCallback(
    (model: GatewayModel) =>
      canManageGatewayModel(model, viewerUserId, resolveTeamCanWrite(model), isPlatformAdmin),
    [viewerUserId, isPlatformAdmin, resolveTeamCanWrite]
  )

  const canDeleteModel = useCallback(
    (model: GatewayModel) =>
      canDeleteGatewayModel(model, viewerUserId, resolveTeamCanWrite(model), isPlatformAdmin),
    [viewerUserId, isPlatformAdmin, resolveTeamCanWrite]
  )

  const canResyncModel = useCallback(
    (model: GatewayModel) =>
      canResyncGatewayModelCapabilities(
        model,
        viewerUserId,
        resolveTeamCanWrite(model),
        isPlatformAdmin
      ),
    [viewerUserId, isPlatformAdmin, resolveTeamCanWrite]
  )

  const hasManageableModels = useMemo(
    () => registryItems.some(canManageModel),
    [registryItems, canManageModel]
  )

  const batchOps = useGatewayModelConnectivityBatchOps({
    scope: 'managed-teams',
    registryItems,
    connectivitySummary,
    listQueryBase,
    canShowBatchOps: hasManageableModels,
    canDeleteModel,
    canResyncModel,
    canManageModel,
  })

  const modelsByTeamId = useMemo(() => groupModelsByTenantId(registryItems), [registryItems])

  const tenantIdsWithModels = useMemo(
    () => new Set(listData?.tenant_ids_with_models ?? []),
    [listData?.tenant_ids_with_models]
  )

  const defaultRegisterTeamId = displayTeams[0]?.id ?? writableCollaborationTeams[0]?.id

  const providerChoices = useMemo(() => {
    const s = new Set<string>(MODEL_PROVIDERS.map((p) => p.id))
    for (const m of registryItems) {
      s.add(m.provider)
    }
    return Array.from(s).sort()
  }, [registryItems])

  const handleTeamSearchChange = useCallback((value: string) => {
    setTeamSearch(value)
    setPage(1)
  }, [])

  const handleModelSearchChange = useCallback((value: string) => {
    setModelSearch(value)
    setPage(1)
  }, [])

  const handleHealthFilterChange = useCallback((filter: HealthFilter) => {
    setHealthFilter(filter)
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
          尚无协作团队。加入协作团队后，可在此查看团队自注册模型；注册与变更需团队管理员权限。
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <ConnectivityBatchTestBanner
        state={batchOps.batchTestState}
        onRetestFailed={batchOps.retestFailed}
        onScrollToFirstFailed={batchOps.scrollToFirstFailed}
      />
      <div className="space-y-2.5 border-b p-3">
        <div className="flex flex-wrap items-center gap-2 sm:gap-3">
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
              placeholder="搜索别名、底模、通道…"
              className="h-8 w-[180px] text-sm"
              aria-label="按模型名称筛选"
            />
            <Select
              value={providerFilter || FILTER_ALL}
              onValueChange={(v) => {
                setProviderFilter(v === FILTER_ALL ? '' : v)
                setPage(1)
              }}
            >
              <SelectTrigger className="h-8 w-[120px] text-xs" aria-label="按接入通道筛选">
                <SelectValue placeholder="全部通道" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={FILTER_ALL}>全部通道</SelectItem>
                {providerChoices.map((id) => (
                  <SelectItem key={id} value={id}>
                    {channelLabel(id)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <RegistryAbilityFilterSelect
              value={abilityFilter}
              onValueChange={(v) => {
                setAbilityFilter(v)
                setPage(1)
              }}
            />
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
        <ConnectivityHealthStrip
          models={registryItems}
          connectivitySummary={connectivitySummary}
          healthFilter={healthFilter}
          onHealthFilterChange={handleHealthFilterChange}
          canWrite={hasManageableModels}
          onTestAll={
            hasManageableModels &&
            (connectivitySummary?.total ?? batchOps.testableItems.length) > 0 &&
            !batchOps.batchBusy
              ? batchOps.handleTestAll
              : undefined
          }
          onTestUntested={
            hasManageableModels &&
            (connectivitySummary?.unknown ?? batchOps.untestedTestableItems.length) > 0 &&
            !batchOps.batchBusy
              ? batchOps.handleTestUntested
              : undefined
          }
          onResyncAll={
            hasManageableModels && (listData?.total ?? 0) > 0 && !batchOps.batchBusy
              ? batchOps.handleResyncAll
              : undefined
          }
          resyncingAll={batchOps.batchResyncing}
          batchBusy={batchOps.batchBusy}
          untestedTestableCount={batchOps.untestedTestableItems.length}
          testingAll={batchOps.batchTesting}
          onDeleteFailed={
            hasManageableModels && batchOps.failedDeletableCount > 0
              ? batchOps.handleDeleteFailed
              : undefined
          }
          deletingFailed={batchOps.batchDeleting}
        />
        <p className="sr-only">{PROVIDER_CHANNEL_FILTER_HINT_GATEWAY}</p>
      </div>
      <CardContent className="p-0">
        <CollaborationTeamsModelsGroupedList
          teams={displayTeams}
          modelsByTeamId={modelsByTeamId}
          tenantIdsWithModels={tenantIdsWithModels}
          requiresSearch={requiresSearch}
          isLoading={showLoading}
          currentPage={page}
          isPlatformAdmin={isPlatformAdmin}
          viewerUserId={viewerUserId}
          updatePendingModelId={updatePendingModelId}
          deletingModelId={deletingModelId}
          onToggleEnabled={handleToggleEnabled}
          onDelete={handleDelete}
        />
      </CardContent>
      {tableFooter ? <div className="border-t px-3 py-2">{tableFooter}</div> : null}

      <ModelBatchDeleteConfirmDialog
        open={batchOps.deleteFailedOpen}
        onOpenChange={batchOps.setDeleteFailedOpen}
        title="删除不可用模型"
        description={
          batchOps.deleteFailedLabel ||
          `确定删除 ${String(batchOps.failedDeletableModels.length)} 个探活失败的模型？将同步更新虚拟 Key / 路由中的模型白名单，并清理相关授权与预算行。此操作不可撤销。`
        }
        pending={batchOps.batchDeleting}
        onConfirm={batchOps.handleConfirmDeleteFailed}
      />

      <ModelBatchDeleteFailedDialog
        open={batchOps.batchFailedOpen}
        onOpenChange={batchOps.setBatchFailedOpen}
        failedItems={batchOps.batchFailedItems}
        title={batchOps.batchFailedDialogTitle}
        description={batchOps.batchFailedDialogDescription}
      />
    </Card>
  )
}
