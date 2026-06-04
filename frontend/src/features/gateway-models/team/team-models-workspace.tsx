import { Suspense, useCallback, useDeferredValue, useEffect, useMemo, useState } from 'react'

import { useQuery, keepPreviousData } from '@tanstack/react-query'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'

import { gatewayApi, fetchAllGatewayModelPages } from '@/api/gateway'
import type { GatewayModel } from '@/api/gateway/models'
import { routesApi } from '@/api/gateway/routes'
import { ConfirmAlertDialog } from '@/components/confirm-alert-dialog'
import { PaginationControls } from '@/components/pagination-controls'
import { Button } from '@/components/ui/button'
import { DropdownMenuItem } from '@/components/ui/dropdown-menu'
import { Switch } from '@/components/ui/switch'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import {
  canBindCredentialForTeamModel,
  canLinkToCredentialDetail,
} from '@/features/gateway-credentials/credential-permissions'
import { credentialSummaryLabel } from '@/features/gateway-credentials/credential-summary-display'
import { useGatewayCredentialDirectory } from '@/features/gateway-credentials/use-credential-directory'
import { ConnectivityBatchTestBanner } from '@/features/gateway-models/connectivity-batch-test-banner'
import {
  type HealthFilter,
  type ModelsPageView,
  type UsagePeriodDays,
  parseModelsPageView,
} from '@/features/gateway-models/constants'
import {
  credentialFilterOptionsFromModels,
  mergeCredentialFilterOptions,
} from '@/features/gateway-models/gateway-model-credential-filter-options'
import {
  canDeleteGatewayModel,
  canManageGatewayModel,
  canResyncGatewayModelCapabilities,
  isConfigManagedSystemModel,
  isModelBatchSelectable,
} from '@/features/gateway-models/gateway-model-permissions'
import { useGatewayModelListBatchOps } from '@/features/gateway-models/hooks/use-gateway-model-connectivity-batch-ops'
import { useGatewayModelMutations } from '@/features/gateway-models/hooks/use-gateway-model-mutations'
import {
  effectiveCapabilities,
  fromGatewayModel,
  GatewayModelBatchBar,
  GatewayModelFlatList,
  GatewayModelListShell,
  GatewayModelListToolbar,
  SYSTEM_ADMIN_CAPABILITIES,
  SHARED_FULL,
} from '@/features/gateway-models/list'
import {
  ModelBatchDeleteConfirmDialog,
  ModelBatchDeleteFailedDialog,
} from '@/features/gateway-models/model-batch-delete-dialogs'
import {
  credentialsSystemBrowseIndexHref,
  credentialDetailAddModelsHref,
  credentialDetailHref,
  credentialsTeamListHref,
  teamModelDetailHref,
} from '@/features/gateway-models/paths'
import { useGatewayModelCredentialFilterOptions } from '@/features/gateway-models/use-managed-team-credential-filter-options'
import {
  gatewayModelsListQueryKey,
  filterResyncableCapabilityModels,
  filterSelectedIdsInView,
  filterTestableConnectivityModels,
  formatBatchDeleteConfirmLabel,
  resolveTeamModelsRegistryScope,
  type TeamModelsListMode,
} from '@/features/gateway-models/utils'
import { combineFetching } from '@/features/gateway-shared/combine-fetching'
import { useGatewayMemberTeamNameMap } from '@/features/gateway-teams/use-gateway-teams'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useGatewayTeamId } from '@/hooks/use-gateway-team-id'
import { lazyWithReload } from '@/lib/lazy-with-reload'
import { Loader2, Plus, Trash2 } from '@/lib/lucide-icons'
import { buildFilterKey, usePaginationPageForFilters } from '@/lib/pagination'
import { useUserStore } from '@/stores/user'
import { MODEL_PROVIDERS } from '@/types/user-model'

import { preloadRegisterModelForm } from './register-model-preload'
import { preloadTeamModelDetailPane } from './team-model-detail-preload'

const RegisterModelForm = lazyWithReload(() =>
  import('./register-model-form').then((m) => ({ default: m.RegisterModelForm }))
)

const registerFormSuspenseFallback = (
  <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground">
    <Loader2 className="h-4 w-4 animate-spin" />
    加载注册表单…
  </div>
)

const EMPTY_REGISTRY_ITEMS: GatewayModel[] = []
const MODELS_PAGE_SIZE = 20

interface TeamModelsWorkspaceProps {
  hideRegisterAction?: boolean
  /** 由父级传入时优先于 URL `view` */
  pageView?: Extract<ModelsPageView, 'list' | 'register'>
  /** `team`：共享 Tab；`system`：平台管理员系统 Tab */
  listMode?: TeamModelsListMode
}

export function TeamModelsWorkspace({
  hideRegisterAction = false,
  pageView: pageViewProp,
  listMode,
}: TeamModelsWorkspaceProps): React.JSX.Element {
  const teamId = useGatewayTeamId()
  const viewerUserId = useUserStore((s) => s.currentUser?.id ?? null)
  const { canWrite, canContribute, isPlatformAdmin } = useGatewayPermission()
  const {
    byId: credentialSummariesById,
    isFetching: directoryFetching,
    refetch: refetchDirectory,
  } = useGatewayCredentialDirectory()
  const teamNameById = useGatewayMemberTeamNameMap()
  const { options: summaryCredentialOptions, isLoading: credentialFilterOptionsLoading } =
    useGatewayModelCredentialFilterOptions(
      listMode === 'system' ? 'system' : 'team-collaboration',
      true
    )
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const credentialFilter = searchParams.get('credentialId') ?? ''
  const highlightModelId = searchParams.get('modelId') ?? ''
  const pageView = pageViewProp ?? parseModelsPageView(searchParams.get('view'))
  const canManageModels = listMode === 'system' ? isPlatformAdmin : true
  const isRegisterView = pageView === 'register' && canManageModels

  const [providerFilter, setProviderFilter] = useState('')
  const [abilityFilter, setAbilityFilter] = useState('')
  const [search, setSearch] = useState('')
  const deferredSearch = useDeferredValue(search)
  const [usageDays, setUsageDays] = useState<UsagePeriodDays>(7)
  const [healthFilter, setHealthFilter] = useState<HealthFilter>('all')
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set())
  const [batchDeleteOpen, setBatchDeleteOpen] = useState(false)
  const [deleteFilteredOpen, setDeleteFilteredOpen] = useState(false)
  const [deletingModelId, setDeletingModelId] = useState<string | null>(null)
  const [updatePendingModelId, setUpdatePendingModelId] = useState<string | null>(null)
  const [rowDeleteOpen, setRowDeleteOpen] = useState(false)
  const [pendingRowDeleteId, setPendingRowDeleteId] = useState<string | null>(null)

  const capabilities = useMemo(() => {
    const preset =
      listMode === 'system'
        ? SYSTEM_ADMIN_CAPABILITIES
        : {
            ...SHARED_FULL,
            scope: 'team' as const,
            deleteAllFilteredFetcher: 'single-team' as const,
          }
    const permContext =
      listMode === 'system'
        ? { canWrite: isPlatformAdmin, canContribute: isPlatformAdmin, isPlatformAdmin }
        : { canWrite, canContribute, isPlatformAdmin }
    const effective = effectiveCapabilities(preset, permContext)
    return {
      ...effective,
      showSystemAdmin: listMode === 'system' && isPlatformAdmin,
    }
  }, [canWrite, canContribute, isPlatformAdmin, listMode])

  const systemPermContext = useMemo(
    () => (listMode === 'system' ? ({ preferSystem: true } as const) : undefined),
    [listMode]
  )
  const batchSelectEnabled = (listMode === 'system' && isPlatformAdmin) || listMode === 'team'

  const registryScope = resolveTeamModelsRegistryScope(listMode, credentialFilter)

  const modelsListFilterKey = useMemo(
    () =>
      buildFilterKey([
        registryScope,
        providerFilter,
        credentialFilter,
        abilityFilter,
        deferredSearch,
        healthFilter,
      ]),
    [registryScope, providerFilter, credentialFilter, abilityFilter, deferredSearch, healthFilter]
  )
  const [page, setPage] = usePaginationPageForFilters(modelsListFilterKey)

  const teamListQueryBase = useMemo(
    () => ({
      registry_scope: registryScope,
      ...(providerFilter ? { provider: providerFilter } : {}),
      ...(credentialFilter ? { credential_id: credentialFilter } : {}),
      ...(abilityFilter ? { type: abilityFilter } : {}),
      ...(deferredSearch.trim() ? { q: deferredSearch.trim() } : {}),
    }),
    [registryScope, providerFilter, credentialFilter, abilityFilter, deferredSearch]
  )

  const goToRegister = useCallback((): void => {
    preloadRegisterModelForm()
    setSearchParams(
      (prev) => {
        const n = new URLSearchParams(prev)
        n.set('view', 'register')
        return n
      },
      { replace: true }
    )
  }, [setSearchParams])

  const goToList = useCallback((): void => {
    setSearchParams(
      (prev) => {
        const n = new URLSearchParams(prev)
        n.delete('view')
        return n
      },
      { replace: true }
    )
  }, [setSearchParams])

  const {
    data: listData,
    isLoading,
    isFetching: listFetching,
    refetch: refetchList,
  } = useQuery({
    queryKey: gatewayModelsListQueryKey(
      teamId,
      registryScope,
      providerFilter,
      credentialFilter,
      page,
      MODELS_PAGE_SIZE,
      deferredSearch,
      healthFilter,
      abilityFilter
    ),
    queryFn: () =>
      gatewayApi.listModels(teamId, {
        registry_scope: registryScope,
        page,
        page_size: MODELS_PAGE_SIZE,
        ...(providerFilter ? { provider: providerFilter } : {}),
        ...(credentialFilter ? { credential_id: credentialFilter } : {}),
        ...(abilityFilter ? { type: abilityFilter } : {}),
        ...(deferredSearch.trim() ? { q: deferredSearch.trim() } : {}),
        ...(healthFilter !== 'all' ? { connectivity: healthFilter } : {}),
      }),
    placeholderData: keepPreviousData,
  })

  const registryItems = listData?.items ?? EMPTY_REGISTRY_ITEMS
  const filteredModels = registryItems
  const connectivitySummary = listData?.connectivity_summary

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
    const fromSummary = credentialSummariesById.get(credentialFilter)?.name
    if (fromSummary) return fromSummary
    const fromModel = registryItems.find((model) => model.credential_id === credentialFilter)
    return fromModel?.credential_name?.trim() ?? null
  }, [credentialFilter, credentialFilterOptions, credentialSummariesById, registryItems])

  useEffect(() => {
    if (!listData) return
    const maxPage = Math.max(1, Math.ceil(listData.total / listData.page_size))
    if (page > maxPage) {
      setPage(maxPage)
    }
  }, [listData, page, setPage])

  const pageRouteNames = useMemo(() => registryItems.map((m) => m.name), [registryItems])
  const pageRouteNamesKey = useMemo(() => buildFilterKey(pageRouteNames), [pageRouteNames])

  const {
    data: usageSummary,
    isLoading: usageLoading,
    isFetching: usageFetching,
    refetch: refetchUsage,
  } = useQuery({
    queryKey: [
      'gateway',
      'models',
      'usage-summary',
      teamId,
      providerFilter,
      usageDays,
      pageRouteNamesKey,
    ],
    queryFn: () =>
      gatewayApi.modelsUsageSummary(teamId, {
        days: usageDays,
        ...(providerFilter ? { provider: providerFilter } : {}),
        ...(pageRouteNames.length > 0 ? { route_names: pageRouteNames } : {}),
      }),
    enabled: !isRegisterView && pageRouteNames.length > 0,
    placeholderData: keepPreviousData,
  })

  const { data: credentials } = useQuery({
    queryKey: ['gateway', 'credentials', teamId],
    queryFn: () => gatewayApi.listCredentials(teamId),
    enabled: isRegisterView && listMode === 'team',
  })

  const { data: routes } = useQuery({
    queryKey: ['gateway', 'routes', teamId],
    queryFn: () => routesApi.listRoutes(teamId),
    enabled: !isRegisterView && listMode === 'team',
  })

  const routeMap = useMemo(() => {
    const map = new Map<string, string>()
    for (const route of routes ?? []) {
      for (const pm of route.primary_models) {
        map.set(pm, route.virtual_model)
      }
    }
    return map
  }, [routes])

  const filterCredentialSummary = credentialFilter
    ? credentialSummariesById.get(credentialFilter)
    : undefined
  const filterCredentialLink = canLinkToCredentialDetail(
    filterCredentialSummary,
    viewerUserId,
    canWrite,
    isPlatformAdmin
  )
  const registerCredentialLocked = isRegisterView && credentialFilter !== ''
  const presetProvider =
    registerCredentialLocked && filterCredentialSummary
      ? filterCredentialSummary.provider
      : providerFilter

  const { data: presets } = useQuery({
    queryKey: ['gateway', 'models', 'presets', teamId, presetProvider],
    queryFn: () =>
      presetProvider
        ? gatewayApi.listModelPresets(teamId, { provider: presetProvider })
        : gatewayApi.listModelPresets(teamId),
    enabled: isRegisterView,
  })

  const activeCredentials = useMemo(
    () =>
      (credentials ?? []).filter((c) => {
        if (listMode === 'system' && c.scope !== 'system') return false
        if (listMode === 'team' && c.scope === 'system') return false
        if (listMode === 'team' && !canBindCredentialForTeamModel(c, viewerUserId, canWrite)) {
          return false
        }
        return c.is_active || (credentialFilter !== '' && c.id === credentialFilter)
      }),
    [credentials, credentialFilter, listMode, viewerUserId, canWrite]
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

  const usageByRouteName = useMemo(() => {
    const m = new Map<string, NonNullable<typeof usageSummary>['items'][number]>()
    for (const row of usageSummary?.items ?? []) {
      m.set(row.route_name, row)
    }
    return m
  }, [usageSummary])

  const providerChoices = useMemo(() => {
    const s = new Set<string>(MODEL_PROVIDERS.map((p) => p.id))
    if (providerFilter === '' && registryItems.length > 0) {
      for (const m of registryItems) {
        s.add(m.provider)
      }
    }
    return Array.from(s).sort()
  }, [registryItems, providerFilter])

  const filteredModelIdSet = useMemo(
    () => new Set(filteredModels.map((m) => m.id)),
    [filteredModels]
  )

  const visibleSelectedIds = useMemo(
    () => filterSelectedIdsInView(selectedIds, filteredModelIdSet),
    [selectedIds, filteredModelIdSet]
  )

  const checkModelBatchSelectable = useCallback(
    (model: (typeof registryItems)[number]) =>
      isModelBatchSelectable(model, viewerUserId, canWrite, isPlatformAdmin, systemPermContext),
    [viewerUserId, canWrite, isPlatformAdmin, systemPermContext]
  )

  const canDeleteModel = useCallback(
    (model: (typeof registryItems)[number]) =>
      canDeleteGatewayModel(model, viewerUserId, canWrite, isPlatformAdmin, systemPermContext),
    [viewerUserId, canWrite, isPlatformAdmin, systemPermContext]
  )

  const canResyncModel = useCallback(
    (model: (typeof registryItems)[number]) =>
      canResyncGatewayModelCapabilities(
        model,
        viewerUserId,
        canWrite,
        isPlatformAdmin,
        systemPermContext
      ),
    [viewerUserId, canWrite, isPlatformAdmin, systemPermContext]
  )

  const canManageModel = useCallback(
    (model: (typeof registryItems)[number]) =>
      canManageGatewayModel(model, viewerUserId, canWrite, isPlatformAdmin, systemPermContext),
    [viewerUserId, canWrite, isPlatformAdmin, systemPermContext]
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
    scope: 'single-team',
    teamId,
    listQueryBase: teamListQueryBase,
    registryItems,
    connectivitySummary,
    credentialId: credentialFilter || undefined,
    canShowBatchOps: hasManageableModels,
    canDeleteModel,
    canResyncModel,
    canManageModel,
    onBatchDeleteSucceeded: handleBatchDeleteSucceeded,
  })

  const isConfigManagedModel = useCallback(
    (model: (typeof registryItems)[number]) => isConfigManagedSystemModel(model, systemPermContext),
    [systemPermContext]
  )

  const { createMutation, deleteModelMutation, updateModelMutation } = useGatewayModelMutations({
    credentialId: credentialFilter || undefined,
    onCreateSuccess: (created) => {
      navigate(
        teamModelDetailHref(teamId, created.id, {
          credentialId: credentialFilter !== '' ? credentialFilter : undefined,
          tab: listMode === 'system' ? 'system' : 'shared',
        })
      )
    },
  })

  const selectedModelsForBatch = useMemo(
    () => filteredModels.filter((m) => visibleSelectedIds.has(m.id)),
    [filteredModels, visibleSelectedIds]
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

  const filteredDeleteCount = listData?.total ?? filteredModels.length

  const filteredDeleteLabel = useMemo((): string => {
    if (filteredDeleteCount <= filteredModels.length) {
      return formatBatchDeleteConfirmLabel(filteredModels.map((m) => m.name))
    }
    return `将删除当前筛选下的全部 ${String(filteredDeleteCount)} 个模型，此操作不可撤销。`
  }, [filteredDeleteCount, filteredModels])

  const listItems = useMemo(() => {
    const sorted = [...filteredModels].sort((a, b) => {
      const aVm = routeMap.get(a.name)
      const bVm = routeMap.get(b.name)
      if (aVm && bVm) {
        if (aVm === bVm) return a.name.localeCompare(b.name)
        return aVm.localeCompare(bVm)
      }
      if (aVm) return -1
      if (bVm) return 1
      return a.name.localeCompare(b.name)
    })
    return sorted.map((m) =>
      fromGatewayModel(m, listMode === 'system' ? 'system' : 'team', routeMap.get(m.name))
    )
  }, [filteredModels, listMode, routeMap])

  const selectableModels = useMemo(
    () => filteredModels.filter(checkModelBatchSelectable),
    [filteredModels, checkModelBatchSelectable]
  )

  const allSelectableSelected =
    selectableModels.length > 0 && selectableModels.every((m) => visibleSelectedIds.has(m.id))
  const someSelectableSelected = selectableModels.some((m) => visibleSelectedIds.has(m.id))

  const handleConfirmDeleteFiltered = useCallback((): void => {
    void (async () => {
      const all = await fetchAllGatewayModelPages(teamId, {
        ...teamListQueryBase,
        ...(healthFilter !== 'all' ? { connectivity: healthFilter } : {}),
      })
      if (all.length === 0) return
      runBatchDelete(all.map((m) => m.id))
    })()
  }, [teamId, teamListQueryBase, healthFilter, runBatchDelete])

  const handleToggleEnabled = useCallback(
    (item: ReturnType<typeof fromGatewayModel>, enabled: boolean) => {
      setUpdatePendingModelId(item.id)
      updateModelMutation.mutate(
        { id: item.id, body: { enabled } },
        {
          onSettled: () => {
            setUpdatePendingModelId(null)
          },
        }
      )
    },
    [updateModelMutation]
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

  const canManageItem = useCallback(
    (item: ReturnType<typeof fromGatewayModel>) => {
      const model = item.source as GatewayModel
      return canManageModel(model)
    },
    [canManageModel]
  )

  const isConfigManagedItem = useCallback(
    (item: ReturnType<typeof fromGatewayModel>) => {
      const model = item.source as GatewayModel
      return isConfigManagedModel(model)
    },
    [isConfigManagedModel]
  )

  const batchDeleteTitle = listMode === 'system' ? '批量删除系统模型' : '批量删除团队模型'

  const handleConfirmBatchDelete = useCallback((): void => {
    if (visibleSelectedIds.size === 0) return
    runBatchDelete([...visibleSelectedIds])
  }, [visibleSelectedIds, runBatchDelete])

  const handleBatchTestSelected = useCallback((): void => {
    handleTestSelected(selectedModelsForBatch)
  }, [handleTestSelected, selectedModelsForBatch])

  const handleBatchResyncSelectedClick = useCallback((): void => {
    handleResyncSelected(selectedModelsForBatch)
  }, [handleResyncSelected, selectedModelsForBatch])

  const registryItemsById = useMemo(() => {
    const map = new Map<string, GatewayModel>()
    for (const model of registryItems) {
      map.set(model.id, model)
    }
    return map
  }, [registryItems])

  const getModelHref = useCallback(
    (modelId: string) =>
      teamModelDetailHref(teamId, modelId, {
        credentialId: credentialFilter !== '' ? credentialFilter : undefined,
        tab: listMode === 'system' ? 'system' : 'shared',
      }),
    [teamId, credentialFilter, listMode]
  )

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
        for (const m of filteredModels) {
          if (!checkModelBatchSelectable(m)) continue
          if (selected) {
            next.add(m.id)
          } else {
            next.delete(m.id)
          }
        }
        return next
      })
    },
    [filteredModels, checkModelBatchSelectable]
  )

  const pendingRowDeleteModel =
    pendingRowDeleteId !== null ? (registryItemsById.get(pendingRowDeleteId) ?? null) : null

  const handleDeleteModel = useCallback((id: string): void => {
    setPendingRowDeleteId(id)
    setRowDeleteOpen(true)
  }, [])

  const handleConfirmRowDelete = useCallback((): void => {
    if (!pendingRowDeleteId) return
    const id = pendingRowDeleteId
    setRowDeleteOpen(false)
    setPendingRowDeleteId(null)
    setDeletingModelId(id)
    deleteModelMutation.mutate(
      { id },
      {
        onSettled: () => {
          setDeletingModelId(null)
        },
      }
    )
  }, [pendingRowDeleteId, deleteModelMutation])

  const clearCredentialFilter = useCallback((): void => {
    setSearchParams(
      (prev) => {
        const n = new URLSearchParams(prev)
        n.delete('credentialId')
        n.delete('modelId')
        return n
      },
      { replace: true }
    )
  }, [setSearchParams])

  const handleCreateSubmit = useCallback(
    (body: Parameters<typeof gatewayApi.createModel>[1]) => {
      createMutation.mutate(body)
    },
    [createMutation]
  )

  const handleRefreshList = useCallback((): void => {
    void Promise.all([refetchList(), refetchUsage(), refetchDirectory()])
  }, [refetchDirectory, refetchList, refetchUsage])

  const isRefreshingList = combineFetching(listFetching, usageFetching, directoryFetching)

  const showEmptyOnboarding =
    !isRegisterView &&
    !isLoading &&
    (listData?.total ?? 0) === 0 &&
    !credentialFilter &&
    !providerFilter &&
    !deferredSearch.trim() &&
    healthFilter === 'all'

  const credentialBanner = credentialFilter ? (
    <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-primary/20 bg-primary/5 px-3 py-2 text-sm">
      <span className="text-muted-foreground">
        按凭据筛选：
        {filterCredentialLink ? (
          <Link
            to={credentialDetailHref(teamId, credentialFilter)}
            className="ml-1 font-medium text-primary underline-offset-4 hover:underline"
          >
            {credentialSummaryLabel(filterCredentialSummary, credentialFilter)}
          </Link>
        ) : (
          <span className="ml-1 font-medium">
            {credentialSummaryLabel(filterCredentialSummary, credentialFilter)}
          </span>
        )}
      </span>
      <div className="flex flex-wrap items-center gap-1">
        {canManageModels &&
        filterCredentialSummary &&
        (filterCredentialSummary.scope !== 'system' || isPlatformAdmin) ? (
          <Button variant="ghost" size="sm" className="h-7 px-2 text-xs" asChild>
            <Link to={credentialDetailAddModelsHref(teamId, credentialFilter)}>添加模型</Link>
          </Button>
        ) : null}
        <Button
          variant="ghost"
          size="sm"
          className="h-7"
          type="button"
          onClick={clearCredentialFilter}
        >
          清除筛选
        </Button>
      </div>
    </div>
  ) : null

  if (isRegisterView) {
    return (
      <div className="space-y-4">
        {credentialBanner}
        <Suspense fallback={registerFormSuspenseFallback}>
          <RegisterModelForm
            presets={presets ?? []}
            credentials={activeCredentials}
            lockCredentialId={registerCredentialLocked ? credentialFilter : undefined}
            lockCredentialLabel={filterCredentialSummary?.name}
            initialProvider={filterCredentialSummary?.provider}
            onSubmit={handleCreateSubmit}
            onCancel={goToList}
            isSubmitting={createMutation.isPending}
          />
        </Suspense>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {showEmptyOnboarding ? (
        <div className="rounded-lg border border-dashed bg-muted/10 p-8">
          <h3 className="text-lg font-semibold">
            {listMode === 'system' ? '配置系统模型供给链' : '配置团队模型供给链'}
          </h3>
          <ol className="mt-3 list-decimal space-y-2 pl-5 text-sm text-muted-foreground">
            <li>
              在{' '}
              <Link
                to={
                  listMode === 'system'
                    ? credentialsSystemBrowseIndexHref(teamId)
                    : credentialsTeamListHref(teamId)
                }
                className="text-primary underline"
              >
                {listMode === 'system' ? '系统凭据' : '凭据管理'}
              </Link>{' '}
              添加并启用{listMode === 'system' ? '系统' : '团队'}凭据
            </li>
            <li>注册第一条模型（别名 → 上游 + 凭据）</li>
            <li>
              在{' '}
              <Link to="/gateway/routes" className="text-primary underline">
                虚拟路由
              </Link>{' '}
              将别名编排为对外虚拟名（可选）
            </li>
          </ol>
          {canManageModels ? (
            <Button
              className="mt-4"
              size="sm"
              onMouseEnter={preloadRegisterModelForm}
              onFocus={preloadRegisterModelForm}
              onClick={goToRegister}
            >
              <Plus className="mr-1.5 h-4 w-4" />
              注册第一个模型
            </Button>
          ) : null}
        </div>
      ) : (
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
            <GatewayModelListToolbar
              capabilities={capabilities}
              search={search}
              onSearchChange={setSearch}
              providerFilter={providerFilter}
              onProviderFilterChange={setProviderFilter}
              abilityFilter={abilityFilter}
              onAbilityFilterChange={setAbilityFilter}
              credentialFilter={credentialFilter}
              onCredentialFilterChange={setCredentialFilter}
              credentialFilterOptions={credentialFilterOptions}
              credentialFilterLoading={credentialFilterOptionsLoading || directoryFetching}
              selectedCredentialName={selectedCredentialName}
              providerChoices={providerChoices}
              healthFilter={healthFilter}
              onHealthFilterChange={setHealthFilter}
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
              onRefresh={handleRefreshList}
              isRefreshing={isRefreshingList}
              onRegister={!hideRegisterAction && canManageModels ? goToRegister : undefined}
              onPreloadRegister={preloadRegisterModelForm}
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
          }
          batchBar={
            batchSelectEnabled && capabilities.batchSelect ? (
              <GatewayModelBatchBar
                capabilities={capabilities}
                selectedCount={visibleSelectedIds.size}
                selectableCount={selectableModels.length}
                allSelectableSelected={allSelectableSelected}
                someSelectableSelected={someSelectableSelected}
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
          isLoading={isLoading}
          isEmpty={!isLoading && filteredModels.length === 0}
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
                title={batchDeleteTitle}
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
          <GatewayModelFlatList
            capabilities={capabilities}
            items={listItems}
            selectedIds={batchSelectEnabled ? visibleSelectedIds : undefined}
            onToggleSelect={batchSelectEnabled ? handleToggleSelect : undefined}
            onToggleSelectAll={batchSelectEnabled ? handleToggleSelectAll : undefined}
            selectableCount={selectableModels.length}
            allSelectableSelected={allSelectableSelected}
            someSelectableSelected={someSelectableSelected}
            highlightModelId={highlightModelId !== '' ? highlightModelId : undefined}
            usageDays={usageDays}
            usageByRouteName={usageByRouteName}
            usageLoading={usageLoading}
            getItemHref={(item) => getModelHref(item.id)}
            onPreloadNavigate={preloadTeamModelDetailPane}
            deletingModelId={deletingModelId}
            onDelete={capabilities.rowDelete ? handleDeleteModel : undefined}
            canBatchSelect={canBatchSelectItem}
            canDelete={canDeleteItem}
            isConfigManaged={isConfigManagedItem}
            renderTrailingActions={(item, { isDeleting }) => {
              if (capabilities.showSystemAdmin) return undefined
              const canManage = canManageItem(item)
              const canDelete = canDeleteItem(item)
              const isUpdating = updatePendingModelId === item.id
              if (!canManage && !canDelete) return undefined
              return (
                <div className="flex items-center gap-2">
                  {canManage && capabilities.rowToggleEnabled !== false ? (
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <div className="flex items-center gap-1.5">
                          <span className="hidden text-xs text-muted-foreground lg:inline">
                            {item.enabled ? '已启用' : '已禁用'}
                          </span>
                          <Switch
                            checked={item.enabled}
                            disabled={isUpdating || isDeleting}
                            aria-label={`${item.enabled ? '禁用' : '启用'} ${item.title}`}
                            onCheckedChange={(checked) => {
                              handleToggleEnabled(item, checked)
                            }}
                          />
                        </div>
                      </TooltipTrigger>
                      <TooltipContent side="left" className="text-xs lg:hidden">
                        {item.enabled ? '点击禁用模型' : '点击启用模型'}
                      </TooltipContent>
                    </Tooltip>
                  ) : null}
                  {canDelete && capabilities.rowDelete !== false ? (
                    <Button
                      type="button"
                      size="icon"
                      variant="ghost"
                      className="h-8 w-8 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                      disabled={isDeleting || isUpdating}
                      aria-label={`删除 ${item.title}`}
                      onClick={() => {
                        handleDeleteModel(item.id)
                      }}
                    >
                      {isDeleting ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Trash2 className="h-4 w-4" />
                      )}
                    </Button>
                  ) : null}
                </div>
              )
            }}
          />
        </GatewayModelListShell>
      )}

      <ConfirmAlertDialog
        open={rowDeleteOpen}
        onOpenChange={(open) => {
          setRowDeleteOpen(open)
          if (!open) {
            setPendingRowDeleteId(null)
          }
        }}
        title={listMode === 'system' ? '删除系统模型' : '删除团队模型'}
        description={
          pendingRowDeleteModel
            ? `确定删除模型「${pendingRowDeleteModel.name}」？将同步更新虚拟 Key / 路由中的模型白名单，并清理相关授权与预算行。此操作不可撤销。`
            : '确定删除该模型？'
        }
        confirmLabel="确认删除"
        pending={deleteModelMutation.isPending}
        onConfirm={handleConfirmRowDelete}
      />
    </div>
  )
}
