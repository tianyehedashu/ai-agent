/**
 * 统一模型工作区：个人 + 团队 + 系统单列表。
 */

import { useCallback, useMemo, useRef, useState } from 'react'
import type React from 'react'

import { useQueryClient } from '@tanstack/react-query'
import { useNavigate, useSearchParams } from 'react-router-dom'

import { ConfirmAlertDialog } from '@/components/confirm-alert-dialog'
import { PaginationControls } from '@/components/pagination-controls'
import { Button } from '@/components/ui/button'
import { DropdownMenuItem } from '@/components/ui/dropdown-menu'
import { ConnectivityBatchTestBanner } from '@/features/gateway-models/connectivity-batch-test-banner'
import type { HealthFilter } from '@/features/gateway-models/constants'
import { CopyModelsToTeamDialog } from '@/features/gateway-models/copy-models-to-team-dialog'
import { preloadGatewayModelDetailPanes } from '@/features/gateway-models/detail/preload'
import { useGatewayModelMutations } from '@/features/gateway-models/hooks/use-gateway-model-mutations'
import { usePersonalModelMutations } from '@/features/gateway-models/hooks/use-personal-model-mutations'
import { effectiveCapabilities } from '@/features/gateway-models/list/capabilities'
import { GatewayModelBatchBar } from '@/features/gateway-models/list/gateway-model-batch-bar'
import { GatewayModelListShell } from '@/features/gateway-models/list/gateway-model-list-shell'
import { SHARED_FULL } from '@/features/gateway-models/list/list-presets'
import type { GatewayModelListItem } from '@/features/gateway-models/list/types'
import {
  ModelBatchDeleteConfirmDialog,
  ModelBatchDeleteFailedDialog,
} from '@/features/gateway-models/model-batch-delete-dialogs'
import {
  formatSingleGatewayModelDeleteDescription,
  resolveGatewayModelDeleteScope,
} from '@/features/gateway-models/model-delete-copy'
import {
  personalModelDetailHref,
  systemModelDetailHref,
  teamModelDetailHref,
  type UnifiedModelsListContext,
} from '@/features/gateway-models/paths'
import { invalidateUnifiedModelsCache } from '@/features/gateway-models/unified/invalidate-unified-models-cache'
import { resolveAddModelTargets } from '@/features/gateway-models/unified/resolve-add-model-targets'
import {
  canBatchImportUnifiedModelItem,
  canDeleteUnifiedModelItem,
  canManageUnifiedModelItem,
  canResyncUnifiedModelItem,
  isConfigManagedUnifiedModelItem,
  type UnifiedModelRowPermissionContext,
} from '@/features/gateway-models/unified/unified-model-row-permissions'
import {
  shouldShowUnifiedAffiliationColumn,
  type UnifiedModelScopeFilter,
} from '@/features/gateway-models/unified/unified-models-filters'
import { UnifiedModelsList } from '@/features/gateway-models/unified/unified-models-list'
import { UnifiedModelsToolbar } from '@/features/gateway-models/unified/unified-models-toolbar'
import { useUnifiedModelsBatchOps } from '@/features/gateway-models/unified/use-unified-models-batch-ops'
import { useUnifiedModelsList } from '@/features/gateway-models/unified/use-unified-models-list'
import {
  filterSelectedIdsInView,
  filterTestableConnectivityModels,
  formatBatchDeleteConfirmLabel,
} from '@/features/gateway-models/utils'
import {
  useGatewayContributorCollaborationTeams,
  useGatewayMemberCollaborationTeams,
  useGatewayTeamNameMap,
  useGatewayTeams,
  useGatewayWritableCollaborationTeams,
} from '@/features/gateway-teams/use-gateway-teams'
import { GATEWAY_FILTER_ALL } from '@/features/gateway-usage/gateway-filter-combobox'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useGatewayTeamId } from '@/hooks/use-gateway-team-id'
import { buildFilterKey, usePaginationPageForFilters } from '@/lib/pagination'
import { useCurrentUser } from '@/stores/user'

const UNIFIED_LIST_CAPABILITIES = {
  ...SHARED_FULL,
  scope: 'team' as const,
  batchSelect: true,
  batchBarMode: 'whenHasItems' as const,
  batchTest: true,
  batchResync: true,
  batchDelete: true,
  batchCopyToTeam: true,
  deleteAllFiltered: true,
  deleteFailed: true,
  rowToggleEnabled: true,
  rowDelete: true,
  connectivityBanner: true,
  groupedByTeam: false,
  teamSearch: false,
  headerSlot: false,
  usageSummary: false,
  layout: 'columns' as const,
  rowNavigation: false,
}

function parseScopeFromUrl(raw: string | null): UnifiedModelScopeFilter {
  if (raw === 'personal' || raw === 'team' || raw === 'system') return raw
  return 'all'
}

export function UnifiedModelsWorkspace(): React.JSX.Element {
  const queryClient = useQueryClient()
  const routeTeamId = useGatewayTeamId()
  const teamNameById = useGatewayTeamNameMap()
  const { data: gatewayTeams = [] } = useGatewayTeams()
  const memberTeams = useGatewayMemberCollaborationTeams()
  const contributorTeams = useGatewayContributorCollaborationTeams()
  const writableTeams = useGatewayWritableCollaborationTeams()
  const currentUser = useCurrentUser()
  const viewerUserId = currentUser?.id ?? null
  const hasAuthSession = currentUser !== null
  const { canWrite, canContribute, isPlatformAdmin } = useGatewayPermission()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const highlightModelId = searchParams.get('modelId') ?? ''
  const credentialFilter = searchParams.get('credentialId') ?? ''
  const teamFilter = searchParams.get('affiliationTeamId') ?? ''

  const [search, setSearch] = useState('')
  const scopeFilter = parseScopeFromUrl(searchParams.get('scope'))
  const [providerFilter, setProviderFilter] = useState('')
  const [healthFilter, setHealthFilter] = useState<HealthFilter>('all')
  const filterKey = buildFilterKey([
    search,
    scopeFilter,
    providerFilter,
    healthFilter,
    credentialFilter,
    teamFilter,
  ])
  const [page, setPage] = usePaginationPageForFilters(filterKey)
  const [updatePendingModelId, setUpdatePendingModelId] = useState<string | null>(null)
  const [deletingModelId, setDeletingModelId] = useState<string | null>(null)
  const [pendingDelete, setPendingDelete] = useState<GatewayModelListItem | null>(null)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set())
  const [batchDeleteOpen, setBatchDeleteOpen] = useState(false)
  const [deleteFilteredOpen, setDeleteFilteredOpen] = useState(false)
  const [copyToTeamOpen, setCopyToTeamOpen] = useState(false)

  const {
    items,
    filteredEntries,
    entriesBeforeHealthFilter,
    isLoading,
    isFetching,
    refetch,
    counts,
    filteredTotal,
    connectivitySummary,
    providerChoices,
    teamIdsWithModels,
    pagination,
  } = useUnifiedModelsList({
    search,
    scopeFilter,
    page,
    providerFilter,
    healthFilter,
    credentialFilter,
    teamFilter,
  })

  const teamsWithModels = useMemo(() => {
    const idSet = new Set(teamIdsWithModels)
    const candidates = isPlatformAdmin ? gatewayTeams : memberTeams
    return candidates.filter((team) => idSet.has(team.id) && team.kind === 'shared')
  }, [gatewayTeams, memberTeams, teamIdsWithModels, isPlatformAdmin])

  const showAffiliationColumn = shouldShowUnifiedAffiliationColumn(scopeFilter, teamFilter)

  const teamById = useMemo(() => {
    const map = new Map(memberTeams.map((t) => [t.id, t] as const))
    const modelTeamIdSet = new Set(teamIdsWithModels)
    for (const team of gatewayTeams) {
      if (modelTeamIdSet.has(team.id) && !map.has(team.id)) {
        map.set(team.id, team)
      }
    }
    return map
  }, [memberTeams, gatewayTeams, teamIdsWithModels])

  const hasActiveFilters =
    scopeFilter !== 'all' ||
    search.trim().length > 0 ||
    providerFilter !== '' ||
    healthFilter !== 'all' ||
    credentialFilter !== '' ||
    teamFilter !== ''

  const { updateMutation, deleteMutation: personalDeleteMutation } = usePersonalModelMutations({
    onUpdateSuccess: () => {
      invalidateUnifiedModelsCache(queryClient)
    },
    onDeleteSuccess: () => {
      invalidateUnifiedModelsCache(queryClient)
    },
  })

  const { updateModelMutation, deleteModelMutation } = useGatewayModelMutations()

  const permissionCtx = useMemo(
    (): UnifiedModelRowPermissionContext => ({
      viewerUserId,
      isPlatformAdmin,
      hasAuthSession,
      teamById,
    }),
    [viewerUserId, isPlatformAdmin, hasAuthSession, teamById]
  )

  const hasManageableModels = useMemo(
    () => entriesBeforeHealthFilter.some((item) => canManageUnifiedModelItem(item, permissionCtx)),
    [entriesBeforeHealthFilter, permissionCtx]
  )

  const handleBatchDeleteSucceeded = useCallback((succeeded: readonly string[]): void => {
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
    untestedTestableItems,
    failedDeletableCount,
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
    canBatchSelect,
    connectivityModels,
  } = useUnifiedModelsBatchOps({
    filteredEntries,
    connectivitySummary,
    permissionCtx,
    canShowBatchOps: hasManageableModels,
    defaultTeamId: routeTeamId,
    onBatchDeleteSucceeded: handleBatchDeleteSucceeded,
  })

  const filteredPageIdSet = useMemo(() => new Set(items.map((m) => m.id)), [items])

  const visibleSelectedIds = useMemo(
    () => filterSelectedIdsInView(selectedIds, filteredPageIdSet),
    [selectedIds, filteredPageIdSet]
  )

  const selectableItems = useMemo(
    () => items.filter((item) => canBatchSelect(item)),
    [items, canBatchSelect]
  )

  const selectedItemsForBatch = useMemo(
    () => items.filter((item) => visibleSelectedIds.has(item.id)),
    [items, visibleSelectedIds]
  )

  const personalTeamId = useMemo(
    () => gatewayTeams.find((team) => team.kind === 'personal')?.id,
    [gatewayTeams]
  )

  const hasImportableModels = useMemo(
    () =>
      entriesBeforeHealthFilter.some((item) => canBatchImportUnifiedModelItem(item, permissionCtx)),
    [entriesBeforeHealthFilter, permissionCtx]
  )

  const selectedImportableItems = useMemo(
    () =>
      selectedItemsForBatch.filter((item) => canBatchImportUnifiedModelItem(item, permissionCtx)),
    [selectedItemsForBatch, permissionCtx]
  )

  const allSelectedImportable =
    selectedItemsForBatch.length > 0 &&
    selectedImportableItems.length === selectedItemsForBatch.length

  const showBatchCopyToTeam =
    canContribute && hasImportableModels && contributorTeams.some((team) => team.kind === 'shared')

  const selectedTestable = useMemo(
    () =>
      filterTestableConnectivityModels(
        selectedItemsForBatch.map((item) => ({
          id: item.id,
          capability: item.capability,
          last_test_status: item.lastTestStatus,
        }))
      ),
    [selectedItemsForBatch]
  )

  const selectedResyncable = useMemo(
    () => selectedItemsForBatch.filter((item) => canResyncUnifiedModelItem(item, permissionCtx)),
    [selectedItemsForBatch, permissionCtx]
  )

  const batchDeleteLabel = useMemo(
    (): string => formatBatchDeleteLabel(selectedItemsForBatch),
    [formatBatchDeleteLabel, selectedItemsForBatch]
  )

  const deletableFilteredEntries = useMemo(
    () => filteredEntries.filter((item) => canBatchSelect(item)),
    [filteredEntries, canBatchSelect]
  )

  const filteredDeleteLabel = useMemo((): string => {
    if (deletableFilteredEntries.length <= items.length) {
      return formatBatchDeleteConfirmLabel(deletableFilteredEntries.map((m) => m.title))
    }
    return `将删除当前筛选下的全部 ${String(deletableFilteredEntries.length)} 个模型，此操作不可撤销。`
  }, [deletableFilteredEntries, items.length])

  const allPageSelectableSelected =
    selectableItems.length > 0 && selectableItems.every((m) => visibleSelectedIds.has(m.id))
  const somePageSelectableSelected = selectableItems.some((m) => visibleSelectedIds.has(m.id))

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
        for (const item of selectableItems) {
          if (selected) {
            next.add(item.id)
          } else {
            next.delete(item.id)
          }
        }
        return next
      })
    },
    [selectableItems]
  )

  const handleConfirmBatchDelete = useCallback((): void => {
    if (visibleSelectedIds.size === 0) return
    runBatchDelete([...visibleSelectedIds])
    setBatchDeleteOpen(false)
  }, [visibleSelectedIds, runBatchDelete])

  const handleConfirmDeleteFiltered = useCallback((): void => {
    if (deletableFilteredEntries.length === 0) return
    runBatchDelete(deletableFilteredEntries.map((item) => item.id))
    setDeleteFilteredOpen(false)
  }, [deletableFilteredEntries, runBatchDelete])

  const permissionCtxRef = useRef(permissionCtx)
  permissionCtxRef.current = permissionCtx

  const canManageItem = useCallback(
    (item: GatewayModelListItem) => canManageUnifiedModelItem(item, permissionCtxRef.current),
    []
  )
  const canDeleteItem = useCallback(
    (item: GatewayModelListItem) => canDeleteUnifiedModelItem(item, permissionCtxRef.current),
    []
  )

  const handleRefresh = useCallback((): void => {
    void refetch()
  }, [refetch])

  const handleBatchTestSelected = useCallback((): void => {
    handleTestSelected(selectedItemsForBatch)
  }, [handleTestSelected, selectedItemsForBatch])

  const handleBatchResyncSelectedClick = useCallback((): void => {
    handleResyncSelected(selectedItemsForBatch)
  }, [handleResyncSelected, selectedItemsForBatch])

  const handleOpenBatchDelete = useCallback((): void => {
    setBatchDeleteOpen(true)
  }, [])

  const handleOpenDeleteFiltered = useCallback((): void => {
    setDeleteFilteredOpen(true)
  }, [])

  const handleScopeFilterChange = useCallback(
    (next: UnifiedModelScopeFilter): void => {
      setSearchParams(
        (prev) => {
          const params = new URLSearchParams(prev)
          if (next === 'all') {
            params.delete('scope')
          } else {
            params.set('scope', next)
          }
          if (next === 'personal' || next === 'system') {
            params.delete('affiliationTeamId')
          }
          return params
        },
        { replace: true }
      )
    },
    [setSearchParams]
  )

  const handleTeamFilterChange = useCallback(
    (next: string): void => {
      setSearchParams(
        (prev) => {
          const params = new URLSearchParams(prev)
          if (!next || next === GATEWAY_FILTER_ALL) {
            params.delete('affiliationTeamId')
          } else {
            params.set('affiliationTeamId', next)
          }
          return params
        },
        { replace: true }
      )
    },
    [setSearchParams]
  )

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
    },
    [setSearchParams]
  )

  const capabilities = useMemo(
    () =>
      effectiveCapabilities(UNIFIED_LIST_CAPABILITIES, {
        canWrite,
        canContribute,
        isPlatformAdmin,
      }),
    [canWrite, canContribute, isPlatformAdmin]
  )

  const showBatchOpsToolbar = capabilities.batchTest === true && hasManageableModels

  const eligibleTeamIds = useMemo(() => {
    const ids = new Set<string>()
    for (const team of writableTeams) {
      ids.add(team.id)
    }
    for (const team of memberTeams) {
      ids.add(team.id)
    }
    return ids
  }, [writableTeams, memberTeams])

  const defaultRegisterTeamId = writableTeams[0]?.id ?? memberTeams[0]?.id
  const canRegisterTeamModel = canWrite || canContribute
  const canRegister = hasAuthSession && (canRegisterTeamModel || isPlatformAdmin)

  const addModelTargets = useMemo(
    () =>
      resolveAddModelTargets({
        scopeFilter,
        routeTeamId,
        credentialId: credentialFilter || undefined,
        affiliationTeamId: teamFilter || undefined,
        canRegisterTeam: canRegisterTeamModel,
        isPlatformAdmin,
        eligibleTeamIds,
        defaultRegisterTeamId,
      }),
    [
      scopeFilter,
      routeTeamId,
      credentialFilter,
      teamFilter,
      canRegisterTeamModel,
      isPlatformAdmin,
      eligibleTeamIds,
      defaultRegisterTeamId,
    ]
  )

  const getItemHref = useCallback(
    (item: GatewayModelListItem): string | undefined => {
      const listContext: UnifiedModelsListContext = {
        ...(scopeFilter !== 'all' ? { scope: scopeFilter } : {}),
        ...(teamFilter !== '' ? { affiliationTeamId: teamFilter } : {}),
      }
      if (item.scope === 'personal') {
        return personalModelDetailHref(routeTeamId, item.id, listContext)
      }
      if (item.scope === 'team') {
        const teamId = item.teamId ?? routeTeamId
        return teamModelDetailHref(teamId, item.id, {
          credentialId: credentialFilter || undefined,
          tab: 'shared',
          listContext,
        })
      }
      return systemModelDetailHref(routeTeamId, item.id, credentialFilter || undefined, listContext)
    },
    [routeTeamId, credentialFilter, scopeFilter, teamFilter]
  )

  const preloadNavigate = useCallback((_item: GatewayModelListItem): void => {
    preloadGatewayModelDetailPanes()
  }, [])

  const handleToggleEnabled = useCallback(
    (item: GatewayModelListItem, enabled: boolean) => {
      setUpdatePendingModelId(item.id)
      if (item.scope === 'personal') {
        updateMutation.mutate(
          { id: item.id, body: { is_active: enabled } },
          {
            onSettled: () => {
              setUpdatePendingModelId(null)
            },
          }
        )
        return
      }
      const teamId = item.teamId ?? routeTeamId
      updateModelMutation.mutate(
        { id: item.id, body: { enabled }, teamId },
        {
          onSettled: () => {
            setUpdatePendingModelId(null)
          },
        }
      )
    },
    [updateMutation, updateModelMutation, routeTeamId]
  )

  const handleConfirmDelete = useCallback(() => {
    if (!pendingDelete) return
    const item = pendingDelete
    setPendingDelete(null)
    setDeletingModelId(item.id)
    if (item.scope === 'personal') {
      personalDeleteMutation.mutate(item.id, {
        onSettled: () => {
          setDeletingModelId(null)
        },
      })
      return
    }
    const teamId = item.teamId ?? routeTeamId
    deleteModelMutation.mutate(
      { id: item.id, teamId },
      {
        onSettled: () => {
          setDeletingModelId(null)
        },
      }
    )
  }, [pendingDelete, personalDeleteMutation, deleteModelMutation, routeTeamId])

  const credentialBanner =
    credentialFilter !== '' ? (
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-primary/20 bg-primary/5 px-3 py-2 text-sm">
        <span className="text-muted-foreground">
          按凭据筛选：
          <span className="ml-1 font-medium">{credentialFilter}</span>
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

  const paginationSlot =
    pagination.total > pagination.page_size ? (
      <div className="border-t px-3 py-2">
        <PaginationControls
          page={pagination.page}
          page_size={pagination.page_size}
          total={pagination.total}
          has_next={pagination.has_next}
          has_prev={pagination.has_prev}
          onPageChange={setPage}
        />
      </div>
    ) : null

  const emptyMessage =
    counts.total === 0
      ? '暂无模型。添加个人或团队模型后即可在虚拟 Key / 路由中使用。'
      : hasActiveFilters
        ? '无匹配模型，请调整筛选条件。'
        : '暂无模型'

  return (
    <>
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
        toolbar={
          <UnifiedModelsToolbar
            search={search}
            onSearchChange={setSearch}
            scopeFilter={scopeFilter}
            onScopeFilterChange={handleScopeFilterChange}
            providerFilter={providerFilter}
            onProviderFilterChange={setProviderFilter}
            providerChoices={providerChoices}
            teamFilter={teamFilter || GATEWAY_FILTER_ALL}
            onTeamFilterChange={handleTeamFilterChange}
            teamsWithModels={teamsWithModels}
            healthFilter={healthFilter}
            onHealthFilterChange={setHealthFilter}
            connectivitySummary={connectivitySummary}
            counts={counts}
            filteredTotal={filteredTotal}
            hasActiveFilters={hasActiveFilters}
            isRefreshing={isFetching}
            onRefresh={handleRefresh}
            showAdd={canRegister && addModelTargets.length > 0}
            addModelTargets={addModelTargets}
            onAddModelTarget={navigate}
            showBatchOps={showBatchOpsToolbar}
            connectivityModels={connectivityModels}
            canWrite={hasManageableModels}
            onTestAll={showBatchOpsToolbar && !batchBusy ? handleTestAll : undefined}
            onTestUntested={showBatchOpsToolbar && !batchBusy ? handleTestUntested : undefined}
            untestedTestableCount={untestedTestableItems.length}
            testingAll={batchTesting}
            batchBusy={batchBusy}
            onResyncAll={
              showBatchOpsToolbar && capabilities.batchResync && !batchBusy
                ? handleResyncAll
                : undefined
            }
            resyncingAll={batchResyncing}
            onDeleteFailed={
              showBatchOpsToolbar && capabilities.deleteFailed && failedDeletableCount > 0
                ? handleDeleteFailed
                : undefined
            }
            deletingFailed={batchDeleting}
            deleteAllFilteredSlot={
              hasManageableModels &&
              capabilities.deleteAllFiltered &&
              deletableFilteredEntries.length > 0 &&
              healthFilter !== 'failed' ? (
                <DropdownMenuItem disabled={batchBusy} onClick={handleOpenDeleteFiltered}>
                  删除当前筛选下全部（{deletableFilteredEntries.length}）
                </DropdownMenuItem>
              ) : undefined
            }
          />
        }
        batchBar={
          capabilities.batchSelect ? (
            <GatewayModelBatchBar
              capabilities={capabilities}
              selectedCount={visibleSelectedIds.size}
              selectableCount={selectableItems.length}
              allSelectableSelected={allPageSelectableSelected}
              someSelectableSelected={somePageSelectableSelected}
              onToggleSelectAll={handleToggleSelectAll}
              onBatchTestSelected={
                hasManageableModels && selectedTestable.length > 0 && !batchBusy
                  ? handleBatchTestSelected
                  : undefined
              }
              onBatchResyncSelected={
                hasManageableModels && selectedResyncable.length > 0 && !batchBusy
                  ? handleBatchResyncSelectedClick
                  : undefined
              }
              onBatchDelete={visibleSelectedIds.size > 0 ? handleOpenBatchDelete : undefined}
              onBatchCopyToTeam={
                showBatchCopyToTeam && visibleSelectedIds.size > 0
                  ? () => {
                      setCopyToTeamOpen(true)
                    }
                  : undefined
              }
              batchCopyToTeamDisabled={!allSelectedImportable}
              batchCopyToTeamDisabledReason={
                !allSelectedImportable ? '部分选中项无导出权限' : undefined
              }
              batchBusy={batchBusy}
              testingAll={batchTesting}
              resyncingAll={batchResyncing}
            />
          ) : undefined
        }
        isLoading={isLoading}
        isEmpty={!isLoading && (counts.total === 0 || filteredTotal === 0)}
        emptySlot={
          <div className="px-4 py-10 text-center text-sm text-muted-foreground">{emptyMessage}</div>
        }
        paginationSlot={paginationSlot ?? undefined}
        dialogsSlot={
          <>
            <ModelBatchDeleteConfirmDialog
              open={batchDeleteOpen}
              onOpenChange={setBatchDeleteOpen}
              title="批量删除模型"
              description={
                batchDeleteLabel ||
                `将删除选中的 ${String(visibleSelectedIds.size)} 个模型，此操作不可撤销。`
              }
              pending={batchDeleting}
              onConfirm={handleConfirmBatchDelete}
            />
            <ModelBatchDeleteConfirmDialog
              open={deleteFilteredOpen}
              onOpenChange={setDeleteFilteredOpen}
              title="删除筛选下全部模型"
              description={filteredDeleteLabel}
              pending={batchDeleting}
              onConfirm={handleConfirmDeleteFiltered}
            />
            <ModelBatchDeleteConfirmDialog
              open={deleteFailedOpen}
              onOpenChange={setDeleteFailedOpen}
              title="删除探活失败模型"
              description={deleteFailedLabel}
              pending={batchDeleting}
              onConfirm={handleConfirmDeleteFailed}
            />
            <ModelBatchDeleteFailedDialog
              open={batchFailedOpen}
              onOpenChange={setBatchFailedOpen}
              title={batchFailedDialogTitle}
              description={batchFailedDialogDescription}
              failedItems={batchFailedItems}
            />
          </>
        }
      >
        {filteredTotal > 0 ? (
          <UnifiedModelsList
            items={items}
            capabilities={capabilities}
            teamNameById={teamNameById}
            showAffiliationColumn={showAffiliationColumn}
            highlightModelId={highlightModelId !== '' ? highlightModelId : undefined}
            getItemHref={getItemHref}
            onPreloadItemNavigate={preloadNavigate}
            canManage={canManageItem}
            canDelete={canDeleteItem}
            canBatchSelect={canBatchSelect}
            isConfigManaged={isConfigManagedUnifiedModelItem}
            deletingModelId={deletingModelId}
            updatePendingModelId={updatePendingModelId}
            onToggleEnabled={handleToggleEnabled}
            onRequestDelete={setPendingDelete}
            selectedIds={selectedIds}
            onToggleSelect={handleToggleSelect}
          />
        ) : null}
      </GatewayModelListShell>

      <ConfirmAlertDialog
        open={pendingDelete !== null}
        onOpenChange={(open) => {
          if (!open) setPendingDelete(null)
        }}
        title="删除模型"
        description={
          pendingDelete
            ? formatSingleGatewayModelDeleteDescription(
                pendingDelete.title,
                resolveGatewayModelDeleteScope(pendingDelete.scope)
              )
            : '确定删除该模型？'
        }
        confirmLabel="确认删除"
        pending={deletingModelId !== null}
        onConfirm={handleConfirmDelete}
      />

      {copyToTeamOpen && allSelectedImportable ? (
        <CopyModelsToTeamDialog
          onOpenChange={(open) => {
            if (!open) setCopyToTeamOpen(false)
          }}
          selectedItems={selectedImportableItems}
          contributorTeams={contributorTeams}
          personalTeamId={personalTeamId}
          viewerUserId={viewerUserId}
        />
      ) : null}
    </>
  )
}
