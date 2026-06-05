/**
 * 团队 Tab：按协作团队分组的模型列表（跨团队聚合）。
 */

import { useCallback, useDeferredValue, useMemo, useState } from 'react'
import type React from 'react'

import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'

import { gatewayApi, fetchAllManagedTeamModelPages } from '@/api/gateway'
import type { GatewayModel } from '@/api/gateway'
import { PaginationControls } from '@/components/pagination-controls'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { DropdownMenuItem } from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import { ConnectivityBatchTestBanner } from '@/features/gateway-models/connectivity-batch-test-banner'
import type { HealthFilter } from '@/features/gateway-models/constants'
import {
  credentialFilterOptionsFromModels,
  mergeCredentialFilterOptions,
} from '@/features/gateway-models/gateway-model-credential-filter-options'
import {
  canDeleteGatewayModel,
  canManageGatewayModel,
  canResyncGatewayModelCapabilities,
  isModelBatchSelectable,
} from '@/features/gateway-models/gateway-model-permissions'
import { useGatewayModelListBatchOps } from '@/features/gateway-models/hooks/use-gateway-model-connectivity-batch-ops'
import { useGatewayModelMutations } from '@/features/gateway-models/hooks/use-gateway-model-mutations'
import {
  effectiveCapabilities,
  fromGatewayModel,
  GatewayModelBatchBar,
  GatewayModelGroupedList,
  GatewayModelListShell,
  GatewayModelListToolbar,
  TEAM_GROUPED_CAPABILITIES,
  buildManagedTeamRouteUsageKey,
} from '@/features/gateway-models/list'
import {
  ModelBatchDeleteConfirmDialog,
  ModelBatchDeleteFailedDialog,
} from '@/features/gateway-models/model-batch-delete-dialogs'
import { teamModelDetailHref, teamModelsRegisterHref } from '@/features/gateway-models/paths'
import { useGatewayModelCredentialFilterOptions } from '@/features/gateway-models/use-managed-team-credential-filter-options'
import { useManagedTeamModelsList } from '@/features/gateway-models/use-managed-team-models-list'
import {
  filterResyncableCapabilityModels,
  filterSelectedIdsInView,
  filterTestableConnectivityModels,
  formatBatchDeleteConfirmLabel,
  resolveGatewayModelTeamId,
} from '@/features/gateway-models/utils'
import { isGatewayTeamWritable } from '@/features/gateway-teams/gateway-team-write-policy'
import {
  groupModelsByTenantId,
  useCollaborationTeamsOverviewResolution,
} from '@/features/gateway-teams/use-collaboration-teams-overview-resolution'
import {
  useGatewayMemberCollaborationTeams,
  useGatewayMemberTeamNameMap,
  useGatewayWritableCollaborationTeams,
} from '@/features/gateway-teams/use-gateway-teams'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { Plus, Search } from '@/lib/lucide-icons'
import { buildFilterKey } from '@/lib/pagination'
import { useCurrentUser } from '@/stores/user'
import { MODEL_PROVIDERS } from '@/types/user-model'

import { preloadTeamModelDetailPane } from './team-model-detail-preload'

export function TeamModelsGroupedWorkspace(): React.JSX.Element {
  const memberCollaborationTeams = useGatewayMemberCollaborationTeams()
  const writableCollaborationTeams = useGatewayWritableCollaborationTeams()
  const teamNameById = useGatewayMemberTeamNameMap()
  const viewerUserId = useCurrentUser()?.id ?? null
  const { canWrite, canContribute, isPlatformAdmin } = useGatewayPermission()
  const [searchParams, setSearchParams] = useSearchParams()
  const credentialFilter = searchParams.get('credentialId') ?? ''
  const highlightModelId = searchParams.get('modelId') ?? ''

  const [teamSearch, setTeamSearch] = useState('')
  const deferredTeamSearch = useDeferredValue(teamSearch)
  const [modelSearch, setModelSearch] = useState('')
  const deferredModelSearch = useDeferredValue(modelSearch)
  const [healthFilter, setHealthFilter] = useState<HealthFilter>('all')
  const [providerFilter, setProviderFilter] = useState('')
  const [abilityFilter, setAbilityFilter] = useState('')
  const [usageDays, setUsageDays] = useState<1 | 7 | 30>(7)
  const [page, setPage] = useState(1)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set())
  const [batchDeleteOpen, setBatchDeleteOpen] = useState(false)
  const [deleteFilteredOpen, setDeleteFilteredOpen] = useState(false)
  const [updatePendingModelId, setUpdatePendingModelId] = useState<string | null>(null)
  const [deletingModelId, setDeletingModelId] = useState<string | null>(null)

  const capabilities = useMemo(
    () =>
      effectiveCapabilities(TEAM_GROUPED_CAPABILITIES, {
        canWrite,
        canContribute,
        isPlatformAdmin,
      }),
    [canWrite, canContribute, isPlatformAdmin]
  )

  const hasCollaborationTeams = memberCollaborationTeams.length > 0
  const teamSearchTrimmed = teamSearch.trim()
  const modelSearchTrimmed = modelSearch.trim()
  const isDeferredTeamSearchStale = deferredTeamSearch.trim() !== teamSearchTrimmed
  const isModelSearchStale = deferredModelSearch.trim() !== modelSearchTrimmed
  const isListSearchStale = isDeferredTeamSearchStale || isModelSearchStale

  const { options: summaryCredentialOptions, isLoading: credentialOptionsLoading } =
    useGatewayModelCredentialFilterOptions('team-collaboration', true)

  const listQueryBase = useMemo(
    () => ({
      ...(deferredTeamSearch.trim() ? { search: deferredTeamSearch.trim() } : {}),
      ...(deferredModelSearch.trim() ? { q: deferredModelSearch.trim() } : {}),
      ...(providerFilter ? { provider: providerFilter } : {}),
      ...(abilityFilter ? { type: abilityFilter } : {}),
      ...(credentialFilter ? { credential_id: credentialFilter } : {}),
    }),
    [deferredTeamSearch, deferredModelSearch, providerFilter, abilityFilter, credentialFilter]
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

  const { teams: displayTeams, requiresSearch } = useCollaborationTeamsOverviewResolution({
    teamSearch,
    queriedTeamCount: listData?.queried_team_count,
    isPlatformAdmin,
    viewerUserId,
    enabled: hasCollaborationTeams,
  })

  const registryItems = useMemo(() => listData?.items ?? [], [listData?.items])
  const connectivitySummary = listData?.connectivity_summary

  const pageRouteNames = useMemo(() => registryItems.map((m) => m.name), [registryItems])
  const pageRouteNamesKey = useMemo(() => buildFilterKey(pageRouteNames), [pageRouteNames])

  const {
    data: usageSummary,
    isLoading: usageLoading,
    isFetching: usageFetching,
  } = useQuery({
    queryKey: [
      'gateway',
      'managed-team-models',
      'usage-summary',
      providerFilter,
      usageDays,
      pageRouteNamesKey,
      deferredTeamSearch,
    ],
    queryFn: () =>
      gatewayApi.managedTeamModelsUsageSummary({
        days: usageDays,
        ...(providerFilter ? { provider: providerFilter } : {}),
        ...(pageRouteNames.length > 0 ? { route_names: pageRouteNames } : {}),
        ...(deferredTeamSearch.trim() ? { search: deferredTeamSearch.trim() } : {}),
      }),
    enabled: hasCollaborationTeams && pageRouteNames.length > 0,
    placeholderData: keepPreviousData,
  })

  const usageByRouteName = useMemo(() => {
    const m = new Map<string, NonNullable<typeof usageSummary>['items'][number]>()
    for (const row of usageSummary?.items ?? []) {
      m.set(buildManagedTeamRouteUsageKey(row.team_id, row.route_name), row)
    }
    return m
  }, [usageSummary])

  const credentialFilterOptions = useMemo(
    () =>
      mergeCredentialFilterOptions(
        summaryCredentialOptions,
        credentialFilterOptionsFromModels(registryItems, teamNameById)
      ),
    [summaryCredentialOptions, registryItems, teamNameById]
  )

  const selectedCredentialName = useMemo(() => {
    if (!credentialFilter) return null
    const fromOption = credentialFilterOptions.find((option) => option.id === credentialFilter)
    if (fromOption) return fromOption.name
    const fromModel = registryItems.find((model) => model.credential_id === credentialFilter)
    return fromModel?.credential_name?.trim() ?? null
  }, [credentialFilter, credentialFilterOptions, registryItems])

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

  const handleBatchDeleteSucceeded = useCallback((succeeded: readonly string[]) => {
    setBatchDeleteOpen(false)
    setDeleteFilteredOpen(false)
    setSelectedIds((prev) => {
      const next = new Set(prev)
      for (const id of succeeded) {
        next.delete(id)
      }
      return next
    })
  }, [])

  const {
    batchTestState,
    batchBusy,
    batchTesting,
    batchDeleting,
    batchResyncing,
    testableItems: batchTestableItems,
    untestedTestableItems: batchUntestedTestableItems,
    failedDeletableCount,
    failedDeletableModels,
    deleteFailedLabel,
    handleTestAll,
    handleTestUntested,
    handleTestSelected,
    handleResyncAll,
    handleResyncSelected,
    handleDeleteFailed,
    handleConfirmDeleteFailed,
    runBatchDelete,
    retestFailed,
    scrollToFirstFailed,
    deleteFailedOpen,
    setDeleteFailedOpen,
    batchFailedOpen,
    setBatchFailedOpen,
    batchFailedItems,
    batchFailedDialogTitle,
    batchFailedDialogDescription,
    formatBatchDeleteLabel,
  } = useGatewayModelListBatchOps({
    scope: 'managed-teams',
    registryItems,
    connectivitySummary,
    listQueryBase,
    canShowBatchOps: hasManageableModels,
    canDeleteModel,
    canResyncModel,
    canManageModel,
    onBatchDeleteSucceeded: handleBatchDeleteSucceeded,
  })

  const itemsByTeamId = useMemo(() => {
    const grouped = groupModelsByTenantId(registryItems)
    const result = new Map<string, ReturnType<typeof fromGatewayModel>[]>()
    for (const [teamId, models] of grouped) {
      result.set(
        teamId,
        models.map((m) => fromGatewayModel(m, 'team'))
      )
    }
    return result
  }, [registryItems])

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

  const filteredModelIdSet = useMemo(() => new Set(registryItems.map((m) => m.id)), [registryItems])

  const visibleSelectedIds = useMemo(
    () => filterSelectedIdsInView(selectedIds, filteredModelIdSet),
    [selectedIds, filteredModelIdSet]
  )

  const checkModelBatchSelectable = useCallback(
    (model: GatewayModel) =>
      isModelBatchSelectable(model, viewerUserId, resolveTeamCanWrite(model), isPlatformAdmin),
    [viewerUserId, isPlatformAdmin, resolveTeamCanWrite]
  )

  const selectableModels = useMemo(
    () => registryItems.filter(checkModelBatchSelectable),
    [registryItems, checkModelBatchSelectable]
  )

  const selectedModelsForBatch = useMemo(
    () => registryItems.filter((m) => visibleSelectedIds.has(m.id)),
    [registryItems, visibleSelectedIds]
  )

  const selectedTestable = useMemo(
    () => filterTestableConnectivityModels(selectedModelsForBatch),
    [selectedModelsForBatch]
  )

  const selectedResyncable = useMemo(
    () => filterResyncableCapabilityModels(selectedModelsForBatch, canResyncModel),
    [selectedModelsForBatch, canResyncModel]
  )

  const batchDeleteLabel = useMemo(
    (): string => formatBatchDeleteLabel(selectedModelsForBatch),
    [formatBatchDeleteLabel, selectedModelsForBatch]
  )

  const filteredDeleteCount = listData?.total ?? registryItems.length

  const filteredDeleteLabel = useMemo((): string => {
    if (filteredDeleteCount <= registryItems.length) {
      return formatBatchDeleteConfirmLabel(registryItems.map((m) => m.name))
    }
    return `将删除当前筛选下的全部 ${String(filteredDeleteCount)} 个团队模型，此操作不可撤销。`
  }, [filteredDeleteCount, registryItems])

  const setCredentialFilter = useCallback(
    (credentialId: string): void => {
      setSearchParams(
        (prev) => {
          const n = new URLSearchParams(prev)
          if (credentialId) {
            n.set('credentialId', credentialId)
          } else {
            n.delete('credentialId')
            n.delete('modelId')
          }
          return n
        },
        { replace: true }
      )
      setPage(1)
    },
    [setSearchParams]
  )

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

  const handleToggleSelect = useCallback((id: string, selected: boolean): void => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (selected) {
        next.add(id)
      } else {
        next.delete(id)
      }
      return next
    })
  }, [])

  const handleToggleSelectAll = useCallback(
    (selected: boolean): void => {
      setSelectedIds((prev) => {
        const next = new Set(prev)
        for (const m of selectableModels) {
          if (selected) {
            next.add(m.id)
          } else {
            next.delete(m.id)
          }
        }
        return next
      })
    },
    [selectableModels]
  )

  const handleConfirmBatchDelete = useCallback((): void => {
    if (visibleSelectedIds.size === 0) return
    runBatchDelete([...visibleSelectedIds])
  }, [visibleSelectedIds, runBatchDelete])

  const handleConfirmDeleteFiltered = useCallback((): void => {
    void (async () => {
      const all = await fetchAllManagedTeamModelPages({
        ...listQueryBase,
        ...(healthFilter !== 'all' ? { connectivity: healthFilter } : {}),
      })
      if (all.length === 0) return
      runBatchDelete(all.map((m) => m.id))
    })()
  }, [listQueryBase, healthFilter, runBatchDelete])

  const handleToggleEnabled = useCallback(
    (item: ReturnType<typeof fromGatewayModel>, teamId: string, enabled: boolean) => {
      setUpdatePendingModelId(item.id)
      updateModelMutation.mutate(
        { id: item.id, body: { enabled }, teamId },
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
    (item: ReturnType<typeof fromGatewayModel>, teamId: string) => {
      setDeletingModelId(item.id)
      deleteModelMutation.mutate(
        { id: item.id, teamId },
        {
          onSettled: () => {
            setDeletingModelId(null)
          },
        }
      )
    },
    [deleteModelMutation]
  )

  const getModelHref = useCallback(
    (teamId: string, modelId: string) =>
      teamModelDetailHref(teamId, modelId, {
        credentialId: credentialFilter !== '' ? credentialFilter : undefined,
        tab: 'shared',
      }),
    [credentialFilter]
  )

  const canBatchSelectItem = useCallback(
    (item: ReturnType<typeof fromGatewayModel>) => {
      const model = item.source as GatewayModel
      return checkModelBatchSelectable(model)
    },
    [checkModelBatchSelectable]
  )

  const canDeleteItem = useCallback(
    (item: ReturnType<typeof fromGatewayModel>) => {
      const model = item.source as GatewayModel
      return canDeleteModel(model)
    },
    [canDeleteModel]
  )

  const handleRefresh = useCallback(() => {
    void refetch()
  }, [refetch])

  const showLoading = isLoading || isListSearchStale
  const summaryLabel =
    listData !== undefined
      ? isPlatformAdmin
        ? `${String(listData.queried_shared_team_count)} 协作团队 · ${String(listData.total)} 模型`
        : `${String(listData.queried_team_count)} 团队 · ${String(listData.total)} 模型`
      : null

  const credentialBanner =
    credentialFilter && capabilities.credentialBanner ? (
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-primary/20 bg-primary/5 px-3 py-2 text-sm">
        <span className="text-muted-foreground">
          按凭据筛选：
          <span className="ml-1 font-medium">{selectedCredentialName ?? credentialFilter}</span>
        </span>
        <Button
          variant="ghost"
          size="sm"
          className="h-7"
          type="button"
          onClick={() => {
            setCredentialFilter('')
          }}
        >
          清除筛选
        </Button>
      </div>
    ) : null

  if (!hasCollaborationTeams) {
    return (
      <div className="rounded-lg border p-6 text-center text-sm text-muted-foreground">
        尚无协作团队。加入协作团队后，可在此查看团队自注册模型，并在自己创建的凭据下注册模型。
      </div>
    )
  }

  const allSelectableSelected =
    selectableModels.length > 0 && selectableModels.every((m) => visibleSelectedIds.has(m.id))
  const someSelectableSelected = selectableModels.some((m) => visibleSelectedIds.has(m.id))

  return (
    <div className="space-y-3">
      <GatewayModelListShell
        capabilities={capabilities}
        bannerSlot={credentialBanner}
        connectivityBanner={
          capabilities.connectivityBanner ? (
            <ConnectivityBatchTestBanner
              state={batchTestState}
              onRetestFailed={retestFailed}
              onScrollToFirstFailed={scrollToFirstFailed}
            />
          ) : undefined
        }
        headerSlot={
          summaryLabel ? (
            <div className="flex flex-wrap items-center gap-2 border-b px-3 py-2">
              <Badge variant="secondary" className="font-normal">
                {summaryLabel}
              </Badge>
              <div className="ml-auto flex items-center gap-2">
                {(canWrite || canContribute) && defaultRegisterTeamId ? (
                  <Button size="sm" asChild>
                    <Link to={teamModelsRegisterHref(defaultRegisterTeamId)}>
                      <Plus className="mr-1.5 h-4 w-4" />
                      添加模型
                    </Link>
                  </Button>
                ) : null}
              </div>
            </div>
          ) : undefined
        }
        toolbar={
          <div className="space-y-3 border-b p-3">
            {capabilities.teamSearch ? (
              <div className="flex flex-wrap items-center gap-2">
                <div className="relative min-w-0 flex-1 basis-[min(100%,200px)] sm:max-w-[220px]">
                  <Search className="pointer-events-none absolute left-2.5 top-2 h-4 w-4 text-muted-foreground" />
                  <Input
                    value={teamSearch}
                    onChange={(e) => {
                      handleTeamSearchChange(e.target.value)
                    }}
                    placeholder="按团队筛选"
                    className="h-8 w-full pl-8 text-sm"
                    aria-label="按团队名称筛选"
                  />
                </div>
              </div>
            ) : null}
            <GatewayModelListToolbar
              capabilities={capabilities}
              search={modelSearch}
              onSearchChange={handleModelSearchChange}
              providerFilter={providerFilter}
              onProviderFilterChange={(v) => {
                setProviderFilter(v)
                setPage(1)
              }}
              abilityFilter={abilityFilter}
              onAbilityFilterChange={(v) => {
                setAbilityFilter(v)
                setPage(1)
              }}
              credentialFilter={credentialFilter}
              onCredentialFilterChange={setCredentialFilter}
              credentialFilterOptions={credentialFilterOptions}
              credentialFilterLoading={credentialOptionsLoading}
              selectedCredentialName={selectedCredentialName}
              providerChoices={providerChoices}
              healthFilter={healthFilter}
              onHealthFilterChange={handleHealthFilterChange}
              connectivitySummary={connectivitySummary}
              allModels={registryItems}
              usageDays={usageDays}
              onUsageDaysChange={setUsageDays}
              canWrite={hasManageableModels}
              onTestAll={
                hasManageableModels &&
                (connectivitySummary?.total ?? batchTestableItems.length) > 0 &&
                !batchBusy
                  ? handleTestAll
                  : undefined
              }
              onTestUntested={
                hasManageableModels &&
                (connectivitySummary?.unknown ?? batchUntestedTestableItems.length) > 0 &&
                !batchBusy
                  ? handleTestUntested
                  : undefined
              }
              onResyncAll={
                hasManageableModels && (listData?.total ?? 0) > 0 && !batchBusy
                  ? handleResyncAll
                  : undefined
              }
              resyncingAll={batchResyncing}
              batchBusy={batchBusy}
              untestedTestableCount={batchUntestedTestableItems.length}
              testingAll={batchTesting}
              onDeleteFailed={
                hasManageableModels && failedDeletableCount > 0 ? handleDeleteFailed : undefined
              }
              deletingFailed={batchDeleting}
              onRefresh={handleRefresh}
              isRefreshing={isFetching || usageFetching}
              deleteAllFilteredSlot={
                hasManageableModels && filteredDeleteCount > 0 && healthFilter !== 'failed' ? (
                  <DropdownMenuItem
                    disabled={batchBusy}
                    onClick={() => {
                      setDeleteFilteredOpen(true)
                    }}
                  >
                    删除当前筛选下全部（{filteredDeleteCount}）
                  </DropdownMenuItem>
                ) : undefined
              }
            />
          </div>
        }
        batchBar={
          capabilities.batchSelect ? (
            <GatewayModelBatchBar
              capabilities={capabilities}
              selectedCount={visibleSelectedIds.size}
              selectableCount={selectableModels.length}
              allSelectableSelected={allSelectableSelected}
              someSelectableSelected={someSelectableSelected}
              onToggleSelectAll={handleToggleSelectAll}
              onBatchTestSelected={
                hasManageableModels && selectedTestable.length > 0 && !batchBusy
                  ? () => {
                      handleTestSelected(selectedModelsForBatch)
                    }
                  : undefined
              }
              onBatchResyncSelected={
                hasManageableModels && selectedResyncable.length > 0 && !batchBusy
                  ? () => {
                      handleResyncSelected(selectedModelsForBatch)
                    }
                  : undefined
              }
              onBatchDelete={
                visibleSelectedIds.size > 0
                  ? () => {
                      setBatchDeleteOpen(true)
                    }
                  : undefined
              }
              batchBusy={batchBusy}
              testingAll={batchTesting}
              resyncingAll={batchResyncing}
            />
          ) : undefined
        }
        isLoading={showLoading && registryItems.length === 0}
        isEmpty={!showLoading && registryItems.length === 0}
        paginationSlot={
          listData && listData.total > 0 ? (
            <div className="border-t px-3 py-2">
              <PaginationControls
                page={listData.page}
                page_size={listData.page_size}
                total={listData.total}
                has_next={listData.has_next}
                has_prev={listData.has_prev}
                onPageChange={setPage}
              />
            </div>
          ) : undefined
        }
        dialogsSlot={
          <>
            <ModelBatchDeleteConfirmDialog
              open={batchDeleteOpen}
              onOpenChange={setBatchDeleteOpen}
              title="批量删除团队模型"
              description={
                batchDeleteLabel ||
                `确定删除已选的 ${String(visibleSelectedIds.size)} 个模型？将同步更新虚拟 Key / 路由中的模型白名单，并清理相关授权与预算行。此操作不可撤销。`
              }
              pending={batchDeleting}
              onConfirm={handleConfirmBatchDelete}
            />
            <ModelBatchDeleteConfirmDialog
              open={deleteFilteredOpen}
              onOpenChange={setDeleteFilteredOpen}
              title="删除当前筛选下的全部模型"
              description={filteredDeleteLabel}
              confirmLabel="全部删除"
              pending={batchDeleting}
              onConfirm={handleConfirmDeleteFiltered}
            />
            <ModelBatchDeleteConfirmDialog
              open={deleteFailedOpen}
              onOpenChange={setDeleteFailedOpen}
              title="删除不可用模型"
              description={
                deleteFailedLabel ||
                `确定删除 ${String(failedDeletableModels.length)} 个探活失败的模型？将同步更新虚拟 Key / 路由中的模型白名单，并清理相关授权与预算行。此操作不可撤销。`
              }
              pending={batchDeleting}
              onConfirm={handleConfirmDeleteFailed}
            />
            <ModelBatchDeleteFailedDialog
              open={batchFailedOpen}
              onOpenChange={setBatchFailedOpen}
              failedItems={batchFailedItems}
              title={batchFailedDialogTitle}
              description={batchFailedDialogDescription}
            />
          </>
        }
      >
        <GatewayModelGroupedList
          capabilities={capabilities}
          teams={displayTeams}
          itemsByTeamId={itemsByTeamId}
          tenantIdsWithModels={tenantIdsWithModels}
          requiresSearch={requiresSearch}
          isLoading={showLoading}
          currentPage={page}
          isPlatformAdmin={isPlatformAdmin}
          canContribute={canContribute}
          viewerUserId={viewerUserId}
          updatePendingModelId={updatePendingModelId}
          deletingModelId={deletingModelId}
          getModelHref={getModelHref}
          onPreloadNavigate={preloadTeamModelDetailPane}
          onToggleEnabled={handleToggleEnabled}
          onDelete={handleDelete}
          canBatchSelect={canBatchSelectItem}
          canDelete={canDeleteItem}
          selectedIds={visibleSelectedIds}
          onBatchSelectChange={handleToggleSelect}
          highlightModelId={highlightModelId !== '' ? highlightModelId : undefined}
          usageDays={usageDays}
          usageByRouteName={usageByRouteName}
          usageLoading={usageLoading}
        />
      </GatewayModelListShell>
    </div>
  )
}
