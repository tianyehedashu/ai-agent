import { Suspense, useCallback, useDeferredValue, useEffect, useMemo, useState } from 'react'

import { keepPreviousData, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'

import { fetchAllPersonalGatewayModels, gatewayApi, type PersonalGatewayModel } from '@/api/gateway'
import { ConfirmAlertDialog } from '@/components/confirm-alert-dialog'
import { PaginationControls } from '@/components/pagination-controls'
import { Button } from '@/components/ui/button'
import { DropdownMenuItem } from '@/components/ui/dropdown-menu'
import { Switch } from '@/components/ui/switch'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { ConnectivityBatchTestBanner } from '@/features/gateway-models/connectivity-batch-test-banner'
import {
  FILTER_ALL,
  type HealthFilter,
  parseModelsPageView,
} from '@/features/gateway-models/constants'
import { useGatewayModelListBatchOps } from '@/features/gateway-models/hooks/use-gateway-model-connectivity-batch-ops'
import {
  invalidatePersonalModelCaches,
  usePersonalModelMutations,
} from '@/features/gateway-models/hooks/use-personal-model-mutations'
import {
  effectiveCapabilities,
  fromPersonalModel,
  GatewayModelBatchBar,
  GatewayModelFlatList,
  GatewayModelListShell,
  GatewayModelListToolbar,
  PERSONAL_LIST_CAPABILITIES,
} from '@/features/gateway-models/list'
import {
  ModelBatchDeleteConfirmDialog,
  ModelBatchDeleteFailedDialog,
} from '@/features/gateway-models/model-batch-delete-dialogs'
import {
  personalModelDetailHref,
  personalModelsRegisterHref,
} from '@/features/gateway-models/paths'
import {
  filterSelectedIdsInView,
  filterTestableConnectivityModels,
  formatBatchDeleteConfirmLabel,
} from '@/features/gateway-models/utils'
import { combineFetching } from '@/features/gateway-shared/combine-fetching'
import { useGatewayTeamId } from '@/hooks/use-gateway-team-id'
import { useToast } from '@/hooks/use-toast'
import { Loader2, Plus, Trash2 } from '@/lib/lucide-icons'
import { buildFilterKey, usePaginationPageForFilters } from '@/lib/pagination'
import { useUserStore } from '@/stores/user'
import { MODEL_PROVIDERS } from '@/types/user-model'

import { PersonalModelForm, type PersonalModelFormValues } from './personal-model-form'
import { preloadPersonalModelDetailPane, preloadPersonalModelForm } from './personal-model-preload'

const LIST_CHANNEL_ALL = FILTER_ALL
const MY_MODELS_PAGE_SIZE = 20

const EMPTY_PERSONAL_ITEMS: PersonalGatewayModel[] = []

const formSuspenseFallback = (
  <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground">
    <Loader2 className="h-4 w-4 animate-spin" />
    加载表单…
  </div>
)

interface PersonalModelsWorkspaceProps {
  /** 由父级传入时优先于 URL `view` */
  pageView?: 'list' | 'register'
}

export function PersonalModelsWorkspace({
  pageView: pageViewProp,
}: PersonalModelsWorkspaceProps): React.JSX.Element {
  const teamId = useGatewayTeamId()
  const hasAuthSession = useUserStore((s) => s.currentUser !== null)
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const pageView = pageViewProp ?? parseModelsPageView(searchParams.get('view'))
  const isRegisterView = pageView === 'register'
  const credentialIdFromUrl = searchParams.get('credentialId') ?? ''
  const credentialFilter = isRegisterView ? '' : credentialIdFromUrl
  const lockCredentialFromUrl = isRegisterView && credentialIdFromUrl !== ''
  const [listChannel, setListChannel] = useState<string>(LIST_CHANNEL_ALL)
  const [abilityFilter, setAbilityFilter] = useState('')
  const [search, setSearch] = useState('')
  const deferredSearch = useDeferredValue(search)
  const [healthFilter, setHealthFilter] = useState<HealthFilter>('all')
  const [usageDays, setUsageDays] = useState<1 | 7 | 30>(7)
  const personalListFilterKey = useMemo(
    () =>
      buildFilterKey([listChannel, abilityFilter, credentialFilter, deferredSearch, healthFilter]),
    [listChannel, abilityFilter, credentialFilter, deferredSearch, healthFilter]
  )
  const [page, setPage] = usePaginationPageForFilters(personalListFilterKey)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set())
  const [batchDeleteOpen, setBatchDeleteOpen] = useState(false)
  const [deleteFilteredOpen, setDeleteFilteredOpen] = useState(false)
  const [rowDeleteOpen, setRowDeleteOpen] = useState(false)
  const [pendingRowDeleteId, setPendingRowDeleteId] = useState<string | null>(null)
  const [updatePendingModelId, setUpdatePendingModelId] = useState<string | null>(null)
  const queryClient = useQueryClient()
  const { toast } = useToast()

  const capabilities = useMemo(
    () =>
      effectiveCapabilities(PERSONAL_LIST_CAPABILITIES, {
        canWrite: hasAuthSession,
        isPlatformAdmin: false,
      }),
    [hasAuthSession]
  )

  const {
    data: credentials = [],
    isFetching: credentialsFetching,
    refetch: refetchCredentials,
  } = useQuery({
    queryKey: ['gateway', 'my-credentials'],
    queryFn: () => gatewayApi.listMyCredentials(),
    enabled: hasAuthSession,
  })

  const activeCredentials = useMemo(() => credentials.filter((c) => c.is_active), [credentials])

  const credentialFilterOptions = useMemo(
    () =>
      credentials
        .filter((c) => c.is_active || c.id === credentialFilter)
        .map((c) => ({ id: c.id, name: c.name, provider: c.provider })),
    [credentials, credentialFilter]
  )

  const selectedCredentialName = useMemo(() => {
    if (!credentialFilter) return null
    return (
      credentialFilterOptions.find((option) => option.id === credentialFilter)?.name ??
      credentials.find((credential) => credential.id === credentialFilter)?.name ??
      null
    )
  }, [credentialFilter, credentialFilterOptions, credentials])

  const setCredentialFilter = useCallback(
    (credentialId: string): void => {
      setSearchParams(
        (prev) => {
          const n = new URLSearchParams(prev)
          if (credentialId) {
            n.set('credentialId', credentialId)
          } else {
            n.delete('credentialId')
          }
          return n
        },
        { replace: true }
      )
    },
    [setSearchParams]
  )

  const personalListQueryBase = useMemo(
    () => ({
      ...(listChannel !== LIST_CHANNEL_ALL ? { provider: listChannel } : {}),
      ...(abilityFilter ? { type: abilityFilter } : {}),
      ...(credentialFilter ? { credential_id: credentialFilter } : {}),
      ...(deferredSearch.trim() ? { q: deferredSearch.trim() } : {}),
    }),
    [listChannel, abilityFilter, credentialFilter, deferredSearch]
  )

  const hasActiveListFilters =
    listChannel !== LIST_CHANNEL_ALL ||
    abilityFilter !== '' ||
    credentialFilter !== '' ||
    healthFilter !== 'all' ||
    deferredSearch.trim() !== ''

  const {
    data: listData,
    isLoading,
    isFetching: listFetching,
    refetch: refetchList,
  } = useQuery({
    queryKey: [
      'gateway',
      'my-models',
      listChannel,
      abilityFilter,
      credentialFilter,
      page,
      deferredSearch,
      healthFilter,
    ],
    queryFn: () =>
      gatewayApi.listMyModels({
        page,
        page_size: MY_MODELS_PAGE_SIZE,
        ...personalListQueryBase,
        ...(healthFilter !== 'all' ? { connectivity: healthFilter } : {}),
      }),
    enabled: hasAuthSession && !isRegisterView,
    placeholderData: keepPreviousData,
  })

  useEffect(() => {
    if (!listData) return
    const maxPage = Math.max(1, Math.ceil(listData.total / listData.page_size))
    if (page > maxPage) {
      setPage(maxPage)
    }
  }, [listData, page, setPage])

  const items = listData?.items ?? EMPTY_PERSONAL_ITEMS
  const connectivitySummary = listData?.connectivity_summary

  const pageRouteNames = useMemo(() => items.map((m) => m.name), [items])
  const pageRouteNamesKey = useMemo(() => buildFilterKey(pageRouteNames), [pageRouteNames])

  const {
    data: usageSummary,
    isLoading: usageLoading,
    isFetching: usageFetching,
  } = useQuery({
    queryKey: ['gateway', 'my-models', 'usage-summary', listChannel, usageDays, pageRouteNamesKey],
    queryFn: () =>
      gatewayApi.myModelsUsageSummary({
        days: usageDays,
        ...(listChannel !== LIST_CHANNEL_ALL ? { provider: listChannel } : {}),
        ...(pageRouteNames.length > 0 ? { route_names: pageRouteNames } : {}),
      }),
    enabled: hasAuthSession && !isRegisterView && pageRouteNames.length > 0,
    placeholderData: keepPreviousData,
  })

  const usageByRouteName = useMemo(() => {
    const m = new Map<string, NonNullable<typeof usageSummary>['items'][number]>()
    for (const row of usageSummary?.items ?? []) {
      m.set(row.route_name, row)
    }
    return m
  }, [usageSummary])

  const listItems = useMemo(() => items.map(fromPersonalModel), [items])

  const goToList = useCallback((): void => {
    setSearchParams(
      (prev) => {
        const n = new URLSearchParams(prev)
        n.set('tab', 'personal')
        n.delete('view')
        n.delete('credentialId')
        return n
      },
      { replace: true }
    )
  }, [setSearchParams])

  const handleRefresh = useCallback((): void => {
    void Promise.all([refetchList(), refetchCredentials()])
  }, [refetchCredentials, refetchList])

  const isRefreshing = combineFetching(listFetching, credentialsFetching, usageFetching)

  const { createMutation, deleteMutation, updateMutation } = usePersonalModelMutations({
    onCreateSuccess: (created) => {
      if (created.length > 0) {
        navigate(personalModelDetailHref(teamId, created[0].id))
        return
      }
      goToList()
    },
  })

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
    failedDeletableCount,
    failedDeletableModels,
    deleteFailedLabel,
    handleTestAll,
    handleTestUntested,
    handleTestSelected,
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
    formatBatchDeleteLabel,
  } = useGatewayModelListBatchOps({
    scope: 'personal',
    registryItems: items,
    connectivitySummary,
    listQueryBase: personalListQueryBase,
    canShowBatchOps: hasAuthSession,
    canDeleteModel: () => true,
    canResyncModel: () => true,
    canManageModel: () => true,
    onBatchDeleteSucceeded: handleBatchDeleteSucceeded,
  })

  const handleImported = useCallback(
    (count: number, modelIds?: string[]): void => {
      invalidatePersonalModelCaches(queryClient)
      goToList()
      const ids = modelIds ?? []
      toast({
        title: `已导入 ${String(count)} 个模型`,
        description: ids.length > 0 ? '正在后台测试新导入模型的连通性…' : undefined,
      })
      if (ids.length > 0) {
        void Promise.all(ids.map((id) => gatewayApi.getMyModel(id)))
          .then((models) => {
            const testable = filterTestableConnectivityModels(models)
            if (testable.length > 0) {
              handleTestSelected(testable)
            }
          })
          .catch(() => {
            toast({
              variant: 'destructive',
              title: '导入成功，但无法启动连通性测试',
            })
          })
      }
    },
    [goToList, queryClient, handleTestSelected, toast]
  )

  const goToRegister = useCallback((): void => {
    preloadPersonalModelForm()
    navigate(personalModelsRegisterHref(teamId))
  }, [navigate, teamId])

  const handleCreateSubmit = useCallback(
    (values: PersonalModelFormValues): void => {
      if (!values.display_name || !values.model_id || !values.credential_id) return
      createMutation.mutate({
        display_name: values.display_name,
        provider: values.provider,
        model_id: values.model_id,
        credential_id: values.credential_id,
        model_types: values.model_types,
      })
    },
    [createMutation]
  )

  const filteredIdSet = useMemo(() => new Set(items.map((m) => m.id)), [items])

  const visibleSelectedIds = useMemo(
    () => filterSelectedIdsInView(selectedIds, filteredIdSet),
    [selectedIds, filteredIdSet]
  )

  const selectedModelsForBatch = useMemo(
    () => items.filter((m) => visibleSelectedIds.has(m.id)),
    [items, visibleSelectedIds]
  )

  const selectedTestable = useMemo(
    () => filterTestableConnectivityModels(selectedModelsForBatch),
    [selectedModelsForBatch]
  )

  const batchDeleteLabel = useMemo(
    (): string => formatBatchDeleteLabel(selectedModelsForBatch),
    [formatBatchDeleteLabel, selectedModelsForBatch]
  )

  const filteredDeleteCount = listData?.total ?? items.length

  const filteredDeleteLabel = useMemo((): string => {
    if (filteredDeleteCount <= items.length) {
      return formatBatchDeleteConfirmLabel(items.map((m) => m.display_name))
    }
    return `将删除当前筛选下的全部 ${String(filteredDeleteCount)} 个个人模型，此操作不可撤销。`
  }, [filteredDeleteCount, items])

  const pendingRowDeleteModel = useMemo(
    () => (pendingRowDeleteId ? (items.find((m) => m.id === pendingRowDeleteId) ?? null) : null),
    [items, pendingRowDeleteId]
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
        for (const m of items) {
          if (selected) {
            next.add(m.id)
          } else {
            next.delete(m.id)
          }
        }
        return next
      })
    },
    [items]
  )

  const handleConfirmBatchDelete = useCallback((): void => {
    if (visibleSelectedIds.size === 0) return
    runBatchDelete([...visibleSelectedIds])
  }, [visibleSelectedIds, runBatchDelete])

  const handleConfirmDeleteFiltered = useCallback((): void => {
    void (async () => {
      const all = await fetchAllPersonalGatewayModels({
        ...personalListQueryBase,
        ...(healthFilter !== 'all' ? { connectivity: healthFilter } : {}),
      })
      if (all.length === 0) return
      runBatchDelete(all.map((m) => m.id))
    })()
  }, [personalListQueryBase, healthFilter, runBatchDelete])

  const handleRowDelete = useCallback((id: string): void => {
    setPendingRowDeleteId(id)
    setRowDeleteOpen(true)
  }, [])

  const handleConfirmRowDelete = useCallback((): void => {
    if (!pendingRowDeleteId) return
    const id = pendingRowDeleteId
    setRowDeleteOpen(false)
    setPendingRowDeleteId(null)
    deleteMutation.mutate(id)
  }, [pendingRowDeleteId, deleteMutation])

  const handleToggleActive = useCallback(
    (item: ReturnType<typeof fromPersonalModel>, enabled: boolean) => {
      setUpdatePendingModelId(item.id)
      updateMutation.mutate(
        { id: item.id, body: { is_active: enabled } },
        {
          onSettled: () => {
            setUpdatePendingModelId(null)
          },
        }
      )
    },
    [updateMutation]
  )

  const providerChoices = useMemo(() => {
    const s = new Set<string>(MODEL_PROVIDERS.map((p) => p.id))
    for (const m of items) {
      s.add(m.provider)
    }
    return Array.from(s).sort()
  }, [items])

  const allFilteredSelected = items.length > 0 && items.every((m) => visibleSelectedIds.has(m.id))
  const someFilteredSelected = items.some((m) => visibleSelectedIds.has(m.id))

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

  if (!hasAuthSession) {
    return <p className="py-8 text-center text-sm text-muted-foreground">请先登录以管理个人模型</p>
  }

  if (isRegisterView) {
    return (
      <Suspense fallback={formSuspenseFallback}>
        <PersonalModelForm
          mode="create"
          credentials={credentials}
          lockCredentialId={lockCredentialFromUrl ? credentialIdFromUrl : undefined}
          initialCredentialId={credentialIdFromUrl || undefined}
          onImported={handleImported}
          onSubmit={handleCreateSubmit}
          onCancel={goToList}
          isSubmitting={createMutation.isPending}
        />
      </Suspense>
    )
  }

  const showEmptyOnboarding = !isLoading && (listData?.total ?? 0) === 0 && !hasActiveListFilters

  return (
    <div className="space-y-4">
      {activeCredentials.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          尚无个人凭据，请先到{' '}
          <Link
            to="/gateway/credentials?tab=personal"
            className="text-primary underline-offset-4 hover:underline"
          >
            凭据管理
          </Link>{' '}
          添加 API Key。
        </p>
      ) : null}

      {showEmptyOnboarding ? (
        <div className="rounded-lg border border-dashed bg-muted/10 p-8">
          <h3 className="text-lg font-semibold">配置个人模型供给链</h3>
          <ol className="mt-3 list-decimal space-y-2 pl-5 text-sm text-muted-foreground">
            <li>
              在{' '}
              <Link
                to="/gateway/credentials?tab=personal"
                className="text-primary underline-offset-4 hover:underline"
              >
                凭据管理
              </Link>{' '}
              添加并启用个人凭据
            </li>
            <li>从上游探测并批量导入，或手动注册单条模型</li>
            <li>
              在{' '}
              <Link
                to={`/gateway/teams/${encodeURIComponent(teamId)}/routes`}
                className="text-primary underline-offset-4 hover:underline"
              >
                虚拟路由
              </Link>{' '}
              编排对外虚拟名（可选）
            </li>
          </ol>
          <Button
            className="mt-4"
            size="sm"
            onClick={goToRegister}
            disabled={activeCredentials.length === 0}
            onMouseEnter={preloadPersonalModelForm}
            onFocus={preloadPersonalModelForm}
          >
            <Plus className="mr-1.5 h-4 w-4" />
            添加第一个模型
          </Button>
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
              providerFilter={listChannel === LIST_CHANNEL_ALL ? '' : listChannel}
              onProviderFilterChange={(v) => {
                setListChannel(v || LIST_CHANNEL_ALL)
              }}
              abilityFilter={abilityFilter}
              onAbilityFilterChange={setAbilityFilter}
              credentialFilter={credentialFilter}
              onCredentialFilterChange={setCredentialFilter}
              credentialFilterOptions={credentialFilterOptions}
              credentialFilterLoading={credentialsFetching}
              selectedCredentialName={selectedCredentialName}
              providerChoices={providerChoices}
              healthFilter={healthFilter}
              onHealthFilterChange={setHealthFilter}
              connectivitySummary={connectivitySummary}
              allModels={items}
              usageDays={usageDays}
              onUsageDaysChange={setUsageDays}
              canWrite={hasAuthSession}
              onTestAll={!batchBusy ? handleTestAll : undefined}
              onTestUntested={!batchBusy ? handleTestUntested : undefined}
              testingAll={batchTesting}
              batchBusy={batchBusy}
              onDeleteFailed={failedDeletableCount > 0 ? handleDeleteFailed : undefined}
              deletingFailed={batchDeleting}
              onRefresh={handleRefresh}
              isRefreshing={isRefreshing}
              onRegister={goToRegister}
              onPreloadRegister={preloadPersonalModelForm}
              deleteAllFilteredSlot={
                filteredDeleteCount > 0 && healthFilter !== 'failed' ? (
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
            capabilities.batchSelect ? (
              <GatewayModelBatchBar
                capabilities={capabilities}
                selectedCount={visibleSelectedIds.size}
                selectableCount={items.length}
                allSelectableSelected={allFilteredSelected}
                someSelectableSelected={someFilteredSelected}
                onToggleSelectAll={handleToggleSelectAll}
                onBatchTestSelected={
                  selectedTestable.length > 0 && !batchBusy
                    ? () => {
                        handleTestSelected(selectedModelsForBatch)
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
              />
            ) : undefined
          }
          isLoading={isLoading}
          isEmpty={!isLoading && (listData?.total ?? 0) === 0 && hasActiveListFilters}
          emptySlot={
            <p className="px-3 py-12 text-center text-sm text-muted-foreground">
              当前筛选下没有匹配的模型，请调整搜索或健康状态筛选。
            </p>
          }
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
                title="批量删除个人模型"
                description={
                  batchDeleteLabel ||
                  `确定删除已选的 ${String(visibleSelectedIds.size)} 个模型？将同步更新虚拟 Key / 路由中的模型白名单，并清理相关授权与预算行。此操作不可撤销。`
                }
                confirmLabel="删除"
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
              />
            </>
          }
        >
          <GatewayModelFlatList
            capabilities={capabilities}
            items={listItems}
            selectedIds={visibleSelectedIds}
            onToggleSelect={handleToggleSelect}
            onToggleSelectAll={handleToggleSelectAll}
            selectableCount={items.length}
            allSelectableSelected={allFilteredSelected}
            someSelectableSelected={someFilteredSelected}
            usageDays={usageDays}
            usageByRouteName={usageByRouteName}
            usageLoading={usageLoading}
            getItemHref={(item) => personalModelDetailHref(teamId, item.id)}
            onPreloadNavigate={preloadPersonalModelDetailPane}
            onDelete={handleRowDelete}
            canBatchSelect={() => true}
            canDelete={() => true}
            renderTrailingActions={(item, { isDeleting }) => {
              const isUpdating = updatePendingModelId === item.id
              return (
                <div className="flex items-center gap-2">
                  {capabilities.rowToggleEnabled !== false ? (
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
                              handleToggleActive(item, checked)
                            }}
                          />
                        </div>
                      </TooltipTrigger>
                      <TooltipContent side="left" className="text-xs lg:hidden">
                        {item.enabled ? '点击禁用模型' : '点击启用模型'}
                      </TooltipContent>
                    </Tooltip>
                  ) : null}
                  {capabilities.rowDelete !== false ? (
                    <Button
                      type="button"
                      size="icon"
                      variant="ghost"
                      className="h-8 w-8 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                      disabled={isDeleting || isUpdating}
                      aria-label={`删除 ${item.title}`}
                      onClick={() => {
                        handleRowDelete(item.id)
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
          if (!open) setPendingRowDeleteId(null)
        }}
        title="删除个人模型"
        description={
          pendingRowDeleteModel
            ? `确定删除模型「${pendingRowDeleteModel.display_name}」？将同步更新虚拟 Key / 路由中的模型白名单，并清理相关授权与预算行。此操作不可撤销。`
            : '确定删除该模型？'
        }
        confirmLabel="删除"
        pending={deleteMutation.isPending}
        onConfirm={handleConfirmRowDelete}
      />
    </div>
  )
}
