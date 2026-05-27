import {
  Suspense,
  useCallback,
  useDeferredValue,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react'

import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'

import {
  fetchAllPersonalGatewayModels,
  gatewayApi,
  type GatewayModelBatchDeleteFailureItem,
  type PersonalGatewayModel,
} from '@/api/gateway'
import { ConfirmAlertDialog } from '@/components/confirm-alert-dialog'
import { PaginationControls } from '@/components/pagination-controls'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { ConnectivityBatchTestBanner } from '@/features/gateway-models/connectivity-batch-test-banner'
import { ConnectivityHealthStrip } from '@/features/gateway-models/connectivity-health-strip'
import {
  FILTER_ALL,
  type HealthFilter,
  parseModelsPageView,
} from '@/features/gateway-models/constants'
import { useChunkedModelBatchDelete } from '@/features/gateway-models/hooks/use-chunked-model-batch-delete'
import { useConnectivityBatchTest } from '@/features/gateway-models/hooks/use-connectivity-batch-test'
import {
  invalidatePersonalModelCaches,
  usePersonalModelMutations,
} from '@/features/gateway-models/hooks/use-personal-model-mutations'
import {
  ModelBatchDeleteConfirmDialog,
  ModelBatchDeleteFailedDialog,
} from '@/features/gateway-models/model-batch-delete-dialogs'
import {
  personalModelDetailHref,
  personalModelsRegisterHref,
} from '@/features/gateway-models/paths'
import { RegistryAbilityFilterSelect } from '@/features/gateway-models/registry-ability-filter-select'
import {
  createBatchConnectivityCachePatcher,
  filterDeletableFailedModels,
  filterSelectedIdsInView,
  filterTestableConnectivityModels,
  filterUntestedConnectivityModels,
  formatBatchDeleteConfirmLabel,
  formatDeleteFailedConfirmLabel,
  type BatchDeleteChunkResult,
} from '@/features/gateway-models/utils'
import { combineFetching } from '@/features/gateway-shared/combine-fetching'
import { GatewayRefreshButton } from '@/features/gateway-shared/gateway-refresh-button'
import { useGatewayTeamId } from '@/hooks/use-gateway-team-id'
import { useToast } from '@/hooks/use-toast'
import { Loader2, Plus, Trash2 } from '@/lib/lucide-icons'
import { useAuthStore } from '@/stores/auth'
import { MODEL_PROVIDERS } from '@/types/user-model'

import { PersonalModelForm, type PersonalModelFormValues } from './personal-model-form'
import { PersonalModelListRow } from './personal-model-list-row'
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
  const token = useAuthStore((s) => s.token)
  const hasAuthSession = Boolean(token)
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const pageView = pageViewProp ?? parseModelsPageView(searchParams.get('view'))
  const isRegisterView = pageView === 'register'
  const credentialIdFromUrl = searchParams.get('credentialId') ?? ''
  const lockCredentialFromUrl = credentialIdFromUrl !== ''
  const [listChannel, setListChannel] = useState<string>(LIST_CHANNEL_ALL)
  const [abilityFilter, setAbilityFilter] = useState('')
  const [search, setSearch] = useState('')
  const deferredSearch = useDeferredValue(search)
  const [page, setPage] = useState(1)
  const [healthFilter, setHealthFilter] = useState<HealthFilter>('all')
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set())
  const [batchDeleteOpen, setBatchDeleteOpen] = useState(false)
  const [deleteFilteredOpen, setDeleteFilteredOpen] = useState(false)
  const [deleteFailedOpen, setDeleteFailedOpen] = useState(false)
  const [rowDeleteOpen, setRowDeleteOpen] = useState(false)
  const [pendingRowDeleteId, setPendingRowDeleteId] = useState<string | null>(null)
  const [batchFailedOpen, setBatchFailedOpen] = useState(false)
  const [batchFailedItems, setBatchFailedItems] = useState<GatewayModelBatchDeleteFailureItem[]>([])
  const queryClient = useQueryClient()
  const { toast } = useToast()

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

  useEffect(() => {
    setPage(1)
  }, [listChannel, abilityFilter, deferredSearch, healthFilter])

  const personalListQueryBase = useMemo(
    () => ({
      ...(listChannel !== LIST_CHANNEL_ALL ? { provider: listChannel } : {}),
      ...(abilityFilter ? { type: abilityFilter } : {}),
      ...(deferredSearch.trim() ? { q: deferredSearch.trim() } : {}),
    }),
    [listChannel, abilityFilter, deferredSearch]
  )

  const hasActiveListFilters =
    listChannel !== LIST_CHANNEL_ALL ||
    abilityFilter !== '' ||
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
  })

  useEffect(() => {
    if (!listData) return
    const maxPage = Math.max(1, Math.ceil(listData.total / listData.page_size))
    if (page > maxPage) {
      setPage(maxPage)
    }
  }, [listData, page])

  const items = listData?.items ?? EMPTY_PERSONAL_ITEMS
  const connectivitySummary = listData?.connectivity_summary

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

  const isRefreshing = combineFetching(listFetching, credentialsFetching)

  const onBatchItemComplete = useMemo(
    () => createBatchConnectivityCachePatcher(queryClient, 'personal'),
    [queryClient]
  )

  const {
    state: batchTestState,
    start: startBatchTest,
    retestFailed,
  } = useConnectivityBatchTest({
    testById: (id) => gatewayApi.testMyModel(id),
    onItemComplete: onBatchItemComplete,
    invalidate: () => {
      invalidatePersonalModelCaches(queryClient)
    },
    onComplete: (failed) => {
      if (failed.length === 0) {
        toast({ title: '批量测试完成' })
      } else {
        toast({
          variant: 'destructive',
          title: '批量测试完成',
          description: `${String(failed.length)} 个模型探活失败`,
        })
      }
    },
  })

  const batchFailedIdsRef = useRef(batchTestState.failedIds)
  batchFailedIdsRef.current = batchTestState.failedIds

  const scrollToFirstFailed = useCallback((): void => {
    const first = batchFailedIdsRef.current[0]
    if (!first) return
    document
      .querySelector(`[data-connectivity-model-id="${first}"]`)
      ?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, [])

  const { createMutation, deleteMutation } = usePersonalModelMutations({
    onCreateSuccess: (created) => {
      if (created.length > 0) {
        navigate(personalModelDetailHref(teamId, created[0].id))
        return
      }
      goToList()
    },
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
              startBatchTest(testable)
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
    [goToList, queryClient, startBatchTest, toast]
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

  const filteredItems = items

  const filteredIdSet = useMemo(() => new Set(filteredItems.map((m) => m.id)), [filteredItems])

  const visibleSelectedIds = useMemo(
    () => filterSelectedIdsInView(selectedIds, filteredIdSet),
    [selectedIds, filteredIdSet]
  )

  const testableItems = useMemo(() => filterTestableConnectivityModels(items), [items])
  const hasTestableModels = testableItems.length > 0
  const untestedTestableItems = useMemo(() => filterUntestedConnectivityModels(items), [items])
  const selectedCount = visibleSelectedIds.size
  const allFilteredSelected =
    filteredItems.length > 0 && filteredItems.every((m) => visibleSelectedIds.has(m.id))
  const someFilteredSelected = filteredItems.some((m) => visibleSelectedIds.has(m.id))

  const selectedModelsForBatch = useMemo(
    () => filteredItems.filter((m) => visibleSelectedIds.has(m.id)),
    [filteredItems, visibleSelectedIds]
  )

  const selectedTestable = useMemo(
    () => filterTestableConnectivityModels(selectedModelsForBatch),
    [selectedModelsForBatch]
  )

  const batchDeleteLabel = useMemo(
    (): string => formatBatchDeleteConfirmLabel(selectedModelsForBatch.map((m) => m.display_name)),
    [selectedModelsForBatch]
  )

  const filteredDeleteCount = listData?.total ?? filteredItems.length

  const filteredDeleteLabel = useMemo((): string => {
    if (filteredDeleteCount <= filteredItems.length) {
      return formatBatchDeleteConfirmLabel(filteredItems.map((m) => m.display_name))
    }
    return `将删除当前筛选下的全部 ${String(filteredDeleteCount)} 个个人模型，此操作不可撤销。`
  }, [filteredDeleteCount, filteredItems])

  const failedDeletableModels = useMemo(
    () => filterDeletableFailedModels(items, () => true),
    [items]
  )

  const failedDeletableCount = connectivitySummary?.failed ?? failedDeletableModels.length

  const deleteFailedLabel = useMemo(
    (): string =>
      formatDeleteFailedConfirmLabel(
        failedDeletableCount,
        failedDeletableModels.map((m) => m.display_name)
      ),
    [failedDeletableCount, failedDeletableModels]
  )

  const pendingRowDeleteModel = useMemo(
    () => (pendingRowDeleteId ? (items.find((m) => m.id === pendingRowDeleteId) ?? null) : null),
    [items, pendingRowDeleteId]
  )

  const handleBatchDeleteComplete = useCallback(
    (result: BatchDeleteChunkResult): void => {
      invalidatePersonalModelCaches(queryClient)
      setBatchDeleteOpen(false)
      setDeleteFilteredOpen(false)
      setDeleteFailedOpen(false)
      setSelectedIds((prev) => {
        const next = new Set(prev)
        for (const id of result.succeeded) {
          next.delete(id)
        }
        return next
      })
      if (result.failed.length > 0) {
        setBatchFailedItems(result.failed)
        setBatchFailedOpen(true)
      } else if (result.succeeded.length > 0) {
        toast({
          title: '批量删除完成',
          description: `已删除 ${String(result.succeeded.length)} 个模型`,
        })
      }
    },
    [queryClient, toast]
  )

  const deletePersonalModelChunk = useCallback(
    (chunk: string[]) => gatewayApi.batchDeleteMyModels(chunk),
    []
  )

  const { batchDeleting, runBatchDelete: runPersonalBatchDelete } = useChunkedModelBatchDelete({
    deleteChunk: deletePersonalModelChunk,
    onComplete: handleBatchDeleteComplete,
  })

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
        for (const m of filteredItems) {
          if (selected) {
            next.add(m.id)
          } else {
            next.delete(m.id)
          }
        }
        return next
      })
    },
    [filteredItems]
  )

  const handleConfirmBatchDelete = useCallback((): void => {
    if (visibleSelectedIds.size === 0) return
    runPersonalBatchDelete([...visibleSelectedIds])
  }, [visibleSelectedIds, runPersonalBatchDelete])

  const handleConfirmDeleteFiltered = useCallback((): void => {
    void (async () => {
      const all = await fetchAllPersonalGatewayModels({
        ...personalListQueryBase,
        ...(healthFilter !== 'all' ? { connectivity: healthFilter } : {}),
      })
      if (all.length === 0) return
      runPersonalBatchDelete(all.map((m) => m.id))
    })()
  }, [personalListQueryBase, healthFilter, runPersonalBatchDelete])

  const handleDeleteFailed = useCallback((): void => {
    if (failedDeletableCount === 0) return
    setDeleteFailedOpen(true)
  }, [failedDeletableCount])

  const handleConfirmDeleteFailed = useCallback((): void => {
    void (async () => {
      const all = await fetchAllPersonalGatewayModels({
        ...personalListQueryBase,
        connectivity: 'failed',
      })
      if (all.length === 0) return
      runPersonalBatchDelete(all.map((m) => m.id))
    })()
  }, [personalListQueryBase, runPersonalBatchDelete])

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

  const handleTestAll = useCallback((): void => {
    void (async () => {
      const all = await fetchAllPersonalGatewayModels(personalListQueryBase)
      const testable = filterTestableConnectivityModels(all)
      if (testable.length === 0) return
      startBatchTest(testable)
    })()
  }, [personalListQueryBase, startBatchTest])

  const handleTestUntested = useCallback((): void => {
    void (async () => {
      const all = await fetchAllPersonalGatewayModels(personalListQueryBase)
      const untested = filterUntestedConnectivityModels(all)
      if (untested.length === 0) return
      startBatchTest(untested)
    })()
  }, [personalListQueryBase, startBatchTest])

  const handleTestSelected = useCallback((): void => {
    if (selectedTestable.length === 0) return
    startBatchTest(selectedTestable)
  }, [selectedTestable, startBatchTest])

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

  const batchTesting = batchTestState.running
  const batchBusy = batchTesting || batchDeleting

  const showEmptyOnboarding = !isLoading && (listData?.total ?? 0) === 0 && !hasActiveListFilters

  return (
    <div className="space-y-4">
      <ConnectivityBatchTestBanner
        state={batchTestState}
        onRetestFailed={retestFailed}
        onScrollToFirstFailed={scrollToFirstFailed}
      />
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

      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="flex w-full flex-col gap-1.5 sm:w-[220px]">
            <Label htmlFor="personal-model-search">搜索</Label>
            <Input
              id="personal-model-search"
              value={search}
              placeholder="名称、模型 ID、通道…"
              className="h-9 w-full"
              onChange={(e) => {
                setSearch(e.currentTarget.value)
              }}
            />
          </div>
          <div className="flex w-full flex-col gap-1.5 sm:w-[220px]">
            <Label htmlFor="personal-model-channel">接入通道</Label>
            <Select
              value={listChannel}
              onValueChange={(v) => {
                setListChannel(v)
              }}
            >
              <SelectTrigger
                id="personal-model-channel"
                className="h-9 w-full"
                aria-label="按接入通道筛选"
              >
                <SelectValue placeholder="全部" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={LIST_CHANNEL_ALL}>全部</SelectItem>
                {MODEL_PROVIDERS.map((p) => (
                  <SelectItem key={p.id} value={p.id}>
                    {p.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex w-full flex-col gap-1.5 sm:w-[220px]">
            <Label htmlFor="personal-model-ability">能力</Label>
            <RegistryAbilityFilterSelect
              id="personal-model-ability"
              value={abilityFilter}
              onValueChange={setAbilityFilter}
              className="h-9 w-full"
            />
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {items.length > 0 || hasActiveListFilters ? (
            <ConnectivityHealthStrip
              models={items}
              connectivitySummary={connectivitySummary}
              healthFilter={healthFilter}
              onHealthFilterChange={setHealthFilter}
              canWrite={hasAuthSession}
              onTestAll={
                (connectivitySummary?.total ?? hasTestableModels) && !batchBusy
                  ? handleTestAll
                  : undefined
              }
              onTestUntested={
                (connectivitySummary?.unknown ?? untestedTestableItems.length) > 0 && !batchBusy
                  ? handleTestUntested
                  : undefined
              }
              untestedTestableCount={connectivitySummary?.unknown ?? untestedTestableItems.length}
              testingAll={batchTesting}
              batchBusy={batchBusy}
              onDeleteFailed={failedDeletableCount > 0 ? handleDeleteFailed : undefined}
              deletingFailed={batchDeleting}
            />
          ) : null}
          <GatewayRefreshButton
            isFetching={isRefreshing}
            ariaLabel="刷新个人模型"
            onRefresh={handleRefresh}
          />
          <Button
            size="sm"
            className={items.length > 0 ? 'ml-auto' : undefined}
            onClick={goToRegister}
            disabled={activeCredentials.length === 0}
            onMouseEnter={preloadPersonalModelForm}
            onFocus={preloadPersonalModelForm}
          >
            <Plus className="mr-1 h-4 w-4" />
            添加模型
          </Button>
        </div>
      </div>

      {filteredDeleteCount > 0 ? (
        <div className="flex flex-wrap items-center gap-3 rounded-lg border bg-muted/20 px-3 py-2">
          <label className="flex cursor-pointer items-center gap-2 text-sm">
            <Checkbox
              checked={allFilteredSelected ? true : someFilteredSelected ? 'indeterminate' : false}
              onCheckedChange={(checked) => {
                handleToggleSelectAll(checked === true)
              }}
              aria-label="全选当前筛选"
            />
            <span className="text-muted-foreground">全选当前筛选（{filteredDeleteCount}）</span>
          </label>
          {selectedCount > 0 ? (
            <span className="text-sm text-muted-foreground">已选 {selectedCount} 项</span>
          ) : null}
          <div className="ml-auto flex flex-wrap gap-2">
            {filteredDeleteCount > 0 && healthFilter !== 'failed' ? (
              <Button
                size="sm"
                variant="outline"
                className="h-8 text-xs"
                disabled={batchBusy}
                onClick={() => {
                  setDeleteFilteredOpen(true)
                }}
              >
                <Trash2 className="mr-1 h-3 w-3" />
                删除当前筛选下全部（{filteredDeleteCount}）
              </Button>
            ) : null}
            {selectedCount > 0 && selectedTestable.length > 0 && !batchBusy ? (
              <Button
                size="sm"
                variant="outline"
                className="h-8 text-xs"
                disabled={batchBusy}
                onClick={handleTestSelected}
              >
                批量测试
              </Button>
            ) : null}
            {selectedCount > 0 ? (
              <Button
                size="sm"
                variant="destructive"
                className="h-8 text-xs"
                disabled={batchBusy}
                onClick={() => {
                  setBatchDeleteOpen(true)
                }}
              >
                <Trash2 className="mr-1 h-3 w-3" />
                批量删除
              </Button>
            ) : null}
          </div>
        </div>
      ) : null}

      {isLoading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : showEmptyOnboarding ? (
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
                to="/gateway/routes"
                className="text-primary underline-offset-4 hover:underline"
              >
                虚拟路由
              </Link>{' '}
              编排对外虚拟名（可选；请先在 Header 切换到个人工作区）
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
      ) : (listData?.total ?? 0) === 0 ? (
        <p className="py-8 text-center text-sm text-muted-foreground">
          当前筛选下没有匹配的模型，请调整搜索或健康状态筛选。
        </p>
      ) : (
        <ul className="divide-y rounded-lg border">
          {filteredItems.map((m) => (
            <PersonalModelListRow
              key={m.id}
              id={m.id}
              displayName={m.display_name}
              provider={m.provider}
              virtualName={m.name}
              modelId={m.model_id}
              modelTypes={m.model_types}
              lastTestStatus={m.last_test_status}
              lastTestedAt={m.last_tested_at}
              lastTestReason={m.last_test_reason}
              detailHref={personalModelDetailHref(teamId, m.id)}
              selected={visibleSelectedIds.has(m.id)}
              onSelectChange={handleToggleSelect}
              onDelete={handleRowDelete}
              onPreloadNavigate={preloadPersonalModelDetailPane}
            />
          ))}
        </ul>
      )}

      {listData && listData.total > 0 ? (
        <PaginationControls
          page={listData.page}
          page_size={listData.page_size}
          total={listData.total}
          has_next={listData.has_next}
          has_prev={listData.has_prev}
          onPageChange={setPage}
          className="pt-2"
        />
      ) : null}

      <ModelBatchDeleteConfirmDialog
        open={batchDeleteOpen}
        onOpenChange={setBatchDeleteOpen}
        title="批量删除个人模型"
        description={
          batchDeleteLabel ||
          `确定删除已选的 ${String(selectedCount)} 个模型？将同步更新虚拟 Key / 路由中的模型白名单，并清理相关授权与预算行。此操作不可撤销。`
        }
        confirmLabel="删除"
        pending={batchDeleting}
        onConfirm={handleConfirmBatchDelete}
      />

      <ModelBatchDeleteConfirmDialog
        open={deleteFilteredOpen}
        onOpenChange={setDeleteFilteredOpen}
        title="删除当前筛选下的全部模型"
        description={
          filteredDeleteLabel ||
          `确定删除当前筛选下的 ${String(filteredItems.length)} 个模型？将同步更新虚拟 Key / 路由中的模型白名单，并清理相关授权与预算行。此操作不可撤销。`
        }
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

      <ModelBatchDeleteFailedDialog
        open={batchFailedOpen}
        onOpenChange={setBatchFailedOpen}
        failedItems={batchFailedItems}
      />
    </div>
  )
}
