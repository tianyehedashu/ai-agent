import { lazy, Suspense, useCallback, useDeferredValue, useMemo, useState } from 'react'

import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'

import { gatewayApi, type GatewayModelBatchDeleteFailureItem } from '@/api/gateway'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  canLinkToCredentialDetail,
  credentialSummaryLabel,
} from '@/features/gateway-credentials/credential-summary-display'
import { useGatewayCredentialDirectory } from '@/features/gateway-credentials/use-credential-directory'
import {
  type HealthFilter,
  type ModelsPageView,
  type UsagePeriodDays,
  parseModelsPageView,
} from '@/features/gateway-models/constants'
import {
  canDeleteGatewayModel,
  isConfigManagedSystemModel,
  isModelBatchSelectable,
} from '@/features/gateway-models/gateway-model-permissions'
import { useGatewayModelMutations } from '@/features/gateway-models/hooks/use-gateway-model-mutations'
import {
  credentialsSystemBrowseIndexHref,
  credentialDetailAddModelsHref,
  credentialDetailHref,
  credentialsTeamListHref,
  teamModelDetailHref,
} from '@/features/gateway-models/paths'
import {
  gatewayModelsListQueryKey,
  invalidateGatewayModelCaches,
  filterTestableConnectivityModels,
  formatBatchDeleteConfirmLabel,
  matchesHealthFilter,
  resolveTeamModelsRegistryScope,
  runBatchConnectivityTests,
  type TeamModelsListMode,
} from '@/features/gateway-models/utils'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useGatewayTeamId } from '@/hooks/use-gateway-team-id'
import { useToast } from '@/hooks/use-toast'
import { Loader2, Plus } from '@/lib/lucide-icons'
import { MODEL_PROVIDERS } from '@/types/user-model'

import { preloadRegisterModelForm } from './register-model-preload'
import { preloadTeamModelDetailPane } from './team-model-detail-preload'

const ModelInventory = lazy(() =>
  import('./model-inventory').then((m) => ({ default: m.ModelInventory }))
)

const RegisterModelForm = lazy(() =>
  import('./register-model-form').then((m) => ({ default: m.RegisterModelForm }))
)

const inventorySuspenseFallback = (
  <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground">
    <Loader2 className="h-4 w-4 animate-spin" />
    加载清单…
  </div>
)

const registerFormSuspenseFallback = (
  <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground">
    <Loader2 className="h-4 w-4 animate-spin" />
    加载注册表单…
  </div>
)

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
  const { canWrite, isAdmin, isPlatformAdmin } = useGatewayPermission()
  const { byId: credentialSummariesById } = useGatewayCredentialDirectory()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const { toast } = useToast()
  const [searchParams, setSearchParams] = useSearchParams()
  const credentialFilter = searchParams.get('credentialId') ?? ''
  const highlightModelId = searchParams.get('modelId') ?? ''
  const pageView = pageViewProp ?? parseModelsPageView(searchParams.get('view'))
  const canManageModels = listMode === 'system' ? isPlatformAdmin : canWrite
  const isRegisterView = pageView === 'register' && canManageModels

  const [providerFilter, setProviderFilter] = useState('')
  const [search, setSearch] = useState('')
  const deferredSearch = useDeferredValue(search)
  const [usageDays, setUsageDays] = useState<UsagePeriodDays>(7)
  const [healthFilter, setHealthFilter] = useState<HealthFilter>('all')
  const [testingAll, setTestingAll] = useState(false)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set())
  const [batchDeleteOpen, setBatchDeleteOpen] = useState(false)
  const [batchFailedOpen, setBatchFailedOpen] = useState(false)
  const [batchFailedItems, setBatchFailedItems] = useState<GatewayModelBatchDeleteFailureItem[]>([])
  const [deletingModelId, setDeletingModelId] = useState<string | null>(null)
  const [rowDeleteOpen, setRowDeleteOpen] = useState(false)
  const [pendingRowDeleteId, setPendingRowDeleteId] = useState<string | null>(null)

  const systemPermContext = useMemo(
    () => (listMode === 'system' ? ({ preferSystem: true } as const) : undefined),
    [listMode]
  )
  const batchSelectEnabled = listMode === 'system' && isPlatformAdmin

  const registryScope = resolveTeamModelsRegistryScope(listMode, credentialFilter)

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

  const { data: items, isLoading } = useQuery({
    queryKey: gatewayModelsListQueryKey(teamId, registryScope, providerFilter, credentialFilter),
    queryFn: () =>
      gatewayApi.listModels(teamId, {
        registry_scope: registryScope,
        ...(providerFilter ? { provider: providerFilter } : {}),
        ...(credentialFilter ? { credential_id: credentialFilter } : {}),
      }),
  })

  const registryItems = useMemo(() => items ?? [], [items])

  const { data: usageSummary, isLoading: usageLoading } = useQuery({
    queryKey: ['gateway', 'models', 'usage-summary', teamId, providerFilter, usageDays],
    queryFn: () =>
      gatewayApi.modelsUsageSummary(teamId, {
        days: usageDays,
        ...(providerFilter ? { provider: providerFilter } : {}),
      }),
    enabled: !isRegisterView,
  })

  const { data: credentials } = useQuery({
    queryKey: ['gateway', 'credentials', teamId],
    queryFn: () => gatewayApi.listCredentials(teamId),
    enabled: isRegisterView && canManageModels,
  })

  const filterCredentialSummary = credentialFilter
    ? credentialSummariesById.get(credentialFilter)
    : undefined
  const filterCredentialLink = canLinkToCredentialDetail(
    filterCredentialSummary,
    isAdmin,
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
        return c.is_active || (credentialFilter !== '' && c.id === credentialFilter)
      }),
    [credentials, credentialFilter, listMode]
  )

  const scopedRouteNames = useMemo(() => {
    const names = new Set<string>()
    for (const m of registryItems) {
      names.add(m.name)
    }
    return names
  }, [registryItems])

  const usageByRouteName = useMemo(() => {
    const m = new Map<string, NonNullable<typeof usageSummary>['items'][number]>()
    for (const row of usageSummary?.items ?? []) {
      if (listMode !== undefined && !scopedRouteNames.has(row.route_name)) continue
      m.set(row.route_name, row)
    }
    return m
  }, [usageSummary, listMode, scopedRouteNames])

  const providerChoices = useMemo(() => {
    const s = new Set<string>(MODEL_PROVIDERS.map((p) => p.id))
    if (providerFilter === '' && registryItems.length > 0) {
      for (const m of registryItems) {
        s.add(m.provider)
      }
    }
    return Array.from(s).sort()
  }, [registryItems, providerFilter])

  const filteredModels = useMemo(() => {
    const q = deferredSearch.trim().toLowerCase()
    return registryItems.filter((m) => {
      if (!matchesHealthFilter(m, healthFilter)) return false
      if (!q) return true
      return (
        m.name.toLowerCase().includes(q) ||
        m.real_model.toLowerCase().includes(q) ||
        m.provider.toLowerCase().includes(q)
      )
    })
  }, [registryItems, healthFilter, deferredSearch])

  const checkModelBatchSelectable = useCallback(
    (model: (typeof registryItems)[number]) =>
      isModelBatchSelectable(model, isPlatformAdmin, systemPermContext),
    [isPlatformAdmin, systemPermContext]
  )

  const canDeleteModel = useCallback(
    (model: (typeof registryItems)[number]) =>
      canDeleteGatewayModel(model, false, isPlatformAdmin, systemPermContext),
    [isPlatformAdmin, systemPermContext]
  )

  const isConfigManagedModel = useCallback(
    (model: (typeof registryItems)[number]) => isConfigManagedSystemModel(model, systemPermContext),
    [systemPermContext]
  )

  const { createMutation, deleteModelMutation, batchDeleteModelsMutation } =
    useGatewayModelMutations({
      credentialId: credentialFilter || undefined,
      onCreateSuccess: (created) => {
        navigate(
          teamModelDetailHref(teamId, created.id, {
            credentialId: credentialFilter !== '' ? credentialFilter : undefined,
            tab: listMode === 'system' ? 'system' : 'shared',
          })
        )
      },
      onBatchDeleteSuccess: (result) => {
        setBatchDeleteOpen(false)
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
        }
      },
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

  const pendingRowDeleteModel = useMemo(
    () =>
      pendingRowDeleteId !== null
        ? (registryItems.find((m) => m.id === pendingRowDeleteId) ?? null)
        : null,
    [registryItems, pendingRowDeleteId]
  )

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
    deleteModelMutation.mutate(id, {
      onSettled: () => {
        setDeletingModelId(null)
      },
    })
  }, [pendingRowDeleteId, deleteModelMutation])

  const selectedModelsForBatch = useMemo(
    () => registryItems.filter((m) => selectedIds.has(m.id)),
    [registryItems, selectedIds]
  )

  const batchDeleteLabel = useMemo(
    (): string => formatBatchDeleteConfirmLabel(selectedModelsForBatch.map((m) => m.name)),
    [selectedModelsForBatch]
  )

  const handleConfirmBatchDelete = useCallback((): void => {
    if (selectedIds.size === 0) return
    batchDeleteModelsMutation.mutate([...selectedIds])
  }, [selectedIds, batchDeleteModelsMutation])

  const getModelHref = useCallback(
    (modelId: string) =>
      teamModelDetailHref(teamId, modelId, {
        credentialId: credentialFilter !== '' ? credentialFilter : undefined,
        tab: listMode === 'system' ? 'system' : 'shared',
      }),
    [teamId, credentialFilter, listMode]
  )

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

  const testableItems = useMemo(
    () => filterTestableConnectivityModels(registryItems),
    [registryItems]
  )

  const handleTestAll = useCallback((): void => {
    if (testableItems.length === 0) return
    void (async (): Promise<void> => {
      setTestingAll(true)
      try {
        await runBatchConnectivityTests(testableItems, (id) => gatewayApi.testModel(teamId, id))
        invalidateGatewayModelCaches(queryClient, {
          credentialId: credentialFilter || undefined,
          usageSummary: true,
        })
        toast({ title: '批量测试完成' })
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e)
        toast({ variant: 'destructive', title: '批量测试中断', description: msg })
      } finally {
        setTestingAll(false)
      }
    })()
  }, [testableItems, queryClient, toast, credentialFilter, teamId])

  const handleCreateSubmit = useCallback(
    (body: Parameters<typeof gatewayApi.createModel>[1]) => {
      createMutation.mutate(body)
    },
    [createMutation]
  )

  const showEmptyOnboarding =
    !isRegisterView && !isLoading && registryItems.length === 0 && !credentialFilter

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
      {credentialBanner}

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
        <>
          {registryItems.length > 0 ? (
            <Suspense fallback={inventorySuspenseFallback}>
              <ModelInventory
                models={filteredModels}
                allModels={registryItems}
                selectedId={null}
                getModelHref={getModelHref}
                isLoading={isLoading}
                search={search}
                onSearchChange={setSearch}
                providerFilter={providerFilter}
                onProviderFilterChange={setProviderFilter}
                providerChoices={providerChoices}
                usageDays={usageDays}
                onUsageDaysChange={setUsageDays}
                usageByRouteName={usageByRouteName}
                usageLoading={usageLoading}
                highlightModelId={highlightModelId !== '' ? highlightModelId : undefined}
                healthFilter={healthFilter}
                onHealthFilterChange={setHealthFilter}
                canWrite={canManageModels}
                onTestAll={canManageModels && testableItems.length > 0 ? handleTestAll : undefined}
                testingAll={testingAll}
                onRegister={!hideRegisterAction && canManageModels ? goToRegister : undefined}
                onPreloadRegister={preloadRegisterModelForm}
                onPreloadRowNavigate={preloadTeamModelDetailPane}
                showSystemAdmin={listMode === 'system' && isPlatformAdmin}
                batchSelectEnabled={batchSelectEnabled}
                selectedIds={selectedIds}
                onToggleSelect={handleToggleSelect}
                onToggleSelectAll={handleToggleSelectAll}
                isModelBatchSelectable={checkModelBatchSelectable}
                canDeleteModel={canDeleteModel}
                isConfigManagedModel={isConfigManagedModel}
                deletingModelId={deletingModelId}
                onDeleteModel={handleDeleteModel}
                batchDeleteOpen={batchDeleteOpen}
                onBatchDeleteOpenChange={setBatchDeleteOpen}
                onConfirmBatchDelete={handleConfirmBatchDelete}
                batchDeletePending={batchDeleteModelsMutation.isPending}
                batchDeleteLabel={batchDeleteLabel}
              />
            </Suspense>
          ) : null}
        </>
      )}

      <AlertDialog
        open={rowDeleteOpen}
        onOpenChange={(open) => {
          setRowDeleteOpen(open)
          if (!open) {
            setPendingRowDeleteId(null)
          }
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除系统模型</AlertDialogTitle>
            <AlertDialogDescription>
              {pendingRowDeleteModel
                ? `确定删除模型「${pendingRowDeleteModel.name}」？将同步更新虚拟 Key / 路由中的模型白名单，并清理相关授权与预算行。此操作不可撤销。`
                : '确定删除该模型？'}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleteModelMutation.isPending}>取消</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              disabled={deleteModelMutation.isPending || !pendingRowDeleteId}
              onClick={handleConfirmRowDelete}
            >
              {deleteModelMutation.isPending ? '删除中…' : '确认删除'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <Dialog open={batchFailedOpen} onOpenChange={setBatchFailedOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>部分模型未能删除</DialogTitle>
            <DialogDescription>以下条目未删除成功，其余已处理。</DialogDescription>
          </DialogHeader>
          <ul className="max-h-60 space-y-2 overflow-y-auto text-sm">
            {batchFailedItems.map((item) => (
              <li key={item.id} className="rounded-md border px-3 py-2">
                <p className="font-mono text-xs text-muted-foreground">{item.id}</p>
                <p className="mt-1 text-destructive">{item.message}</p>
              </li>
            ))}
          </ul>
          <DialogFooter>
            <Button
              type="button"
              onClick={() => {
                setBatchFailedOpen(false)
              }}
            >
              关闭
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
