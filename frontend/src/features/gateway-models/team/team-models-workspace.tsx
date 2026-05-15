import { lazy, Suspense, useCallback, useDeferredValue, useMemo, useState } from 'react'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2, Plus } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'

import { gatewayApi, type GatewayModelUpdateBody } from '@/api/gateway'
import { Button } from '@/components/ui/button'
import {
  type HealthFilter,
  type TeamModelsView,
  type UsagePeriodDays,
  TESTABLE_CAPABILITIES,
  parseTeamModelsView,
} from '@/features/gateway-models/constants'
import {
  matchesHealthFilter,
  pickInspectorModelId,
  runWithConcurrency,
} from '@/features/gateway-models/utils'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useToast } from '@/hooks/use-toast'
import { MODEL_PROVIDERS } from '@/types/user-model'

import { ModelInspector } from './model-inspector'
import { ModelInventory } from './model-inventory'

const RegisterModelForm = lazy(() =>
  import('./register-model-form').then((m) => ({ default: m.RegisterModelForm }))
)

function preloadRegisterModelForm(): void {
  void import('./register-model-form')
}

const BATCH_TEST_CONCURRENCY = 3

interface TeamModelsWorkspaceProps {
  /** 深链选中模型 id（/gateway/models/:modelId 或 query） */
  initialModelId?: string
  /** 主列表页 Tab 栏已提供「注册模型」子 Tab */
  hideRegisterAction?: boolean
  /** 由父级 Tabs 传入时优先于 URL `view` */
  teamView?: TeamModelsView
}

export function TeamModelsWorkspace({
  initialModelId,
  hideRegisterAction = false,
  teamView: teamViewProp,
}: TeamModelsWorkspaceProps): React.JSX.Element {
  const { canWrite } = useGatewayPermission()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [searchParams, setSearchParams] = useSearchParams()
  const credentialFilter = searchParams.get('credentialId') ?? ''
  const highlightModelId = searchParams.get('modelId') ?? initialModelId ?? ''
  const teamView = teamViewProp ?? parseTeamModelsView(searchParams.get('view'))
  const isRegisterView = teamView === 'register' && canWrite

  const [pinnedId, setPinnedId] = useState<string | null>(initialModelId ?? null)
  const [providerFilter, setProviderFilter] = useState('')
  const [search, setSearch] = useState('')
  const deferredSearch = useDeferredValue(search)
  const [usageDays, setUsageDays] = useState<UsagePeriodDays>(7)
  const [healthFilter, setHealthFilter] = useState<HealthFilter>('all')
  const [testingAll, setTestingAll] = useState(false)

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
    queryKey: ['gateway', 'models', providerFilter, credentialFilter],
    queryFn: () =>
      gatewayApi.listModels({
        ...(providerFilter ? { provider: providerFilter } : {}),
        ...(credentialFilter ? { credential_id: credentialFilter } : {}),
      }),
  })

  const { data: usageSummary, isLoading: usageLoading } = useQuery({
    queryKey: ['gateway', 'models', 'usage-summary', providerFilter, usageDays],
    queryFn: () =>
      gatewayApi.modelsUsageSummary({
        days: usageDays,
        ...(providerFilter ? { provider: providerFilter } : {}),
      }),
    enabled: !isRegisterView,
  })

  const needsSecondaryData = isRegisterView || pinnedId !== null || (items?.length ?? 0) > 0

  const { data: routes } = useQuery({
    queryKey: ['gateway', 'routes'],
    queryFn: () => gatewayApi.listRoutes(),
    enabled: !isRegisterView && pinnedId !== null,
  })

  const { data: presets } = useQuery({
    queryKey: ['gateway', 'models', 'presets', providerFilter],
    queryFn: () =>
      providerFilter
        ? gatewayApi.listModelPresets({ provider: providerFilter })
        : gatewayApi.listModelPresets(),
    enabled: isRegisterView,
  })

  const { data: credentials } = useQuery({
    queryKey: ['gateway', 'credentials'],
    queryFn: () => gatewayApi.listCredentials(),
    enabled: needsSecondaryData,
  })

  const activeCredentials = useMemo(
    () => (credentials ?? []).filter((c) => c.is_active),
    [credentials]
  )

  const credentialsById = useMemo(() => {
    const m = new Map<string, NonNullable<typeof credentials>[number]>()
    for (const c of credentials ?? []) {
      m.set(c.id, c)
    }
    return m
  }, [credentials])

  const usageByRouteName = useMemo(() => {
    const m = new Map<string, NonNullable<typeof usageSummary>['items'][number]>()
    for (const row of usageSummary?.items ?? []) {
      m.set(row.route_name, row)
    }
    return m
  }, [usageSummary])

  const providerChoices = useMemo(() => {
    const s = new Set<string>(MODEL_PROVIDERS.map((p) => p.id))
    if (providerFilter === '' && items?.length) {
      for (const m of items) {
        s.add(m.provider)
      }
    }
    return Array.from(s).sort()
  }, [items, providerFilter])

  const filteredModels = useMemo(() => {
    const q = deferredSearch.trim().toLowerCase()
    return (items ?? []).filter((m) => {
      if (!matchesHealthFilter(m, healthFilter)) return false
      if (!q) return true
      return (
        m.name.toLowerCase().includes(q) ||
        m.real_model.toLowerCase().includes(q) ||
        m.provider.toLowerCase().includes(q)
      )
    })
  }, [items, healthFilter, deferredSearch])

  const preferredModelId = highlightModelId !== '' ? highlightModelId : (initialModelId ?? null)

  const selectedId = useMemo(() => {
    if (isRegisterView || isLoading) return pinnedId
    return pickInspectorModelId(filteredModels, pinnedId, preferredModelId)
  }, [isRegisterView, isLoading, filteredModels, pinnedId, preferredModelId])

  const selectedModel = useMemo(
    () => (items ?? []).find((m) => m.id === selectedId) ?? null,
    [items, selectedId]
  )

  const createMutation = useMutation({
    mutationFn: gatewayApi.createModel,
    onSuccess: (created) => {
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'models'] })
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'models', 'usage-summary'] })
      goToList()
      setPinnedId(created.id)
      toast({ title: '模型已注册' })
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '注册失败', description: e.message })
    },
  })

  const updateModelMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: GatewayModelUpdateBody }) =>
      gatewayApi.updateModel(id, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'models'] })
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'models', 'usage-summary'] })
      toast({ title: '模型已更新' })
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '更新失败', description: e.message })
    },
  })

  const testMutation = useMutation({
    mutationFn: (id: string) => gatewayApi.testModel(id),
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'models'] })
      if (result.success) {
        toast({ title: '连接成功', description: result.message })
      } else {
        toast({ variant: 'destructive', title: '连接失败', description: result.message })
      }
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '测试出错', description: e.message })
    },
  })

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

  const handleTestAll = useCallback(async (): Promise<void> => {
    const testable = (items ?? []).filter((m) => TESTABLE_CAPABILITIES.has(m.capability))
    if (testable.length === 0) return
    setTestingAll(true)
    try {
      await runWithConcurrency(testable, BATCH_TEST_CONCURRENCY, (m) => gatewayApi.testModel(m.id))
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'models'] })
      toast({ title: '批量测试完成' })
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      toast({ variant: 'destructive', title: '批量测试中断', description: msg })
    } finally {
      setTestingAll(false)
    }
  }, [items, queryClient, toast])

  const handleSelect = useCallback((id: string): void => {
    setPinnedId(id)
  }, [])

  const handleTest = useCallback(
    (id: string): void => {
      testMutation.mutate(id)
    },
    [testMutation]
  )

  const handleSave = useCallback(
    (id: string, body: GatewayModelUpdateBody): void => {
      updateModelMutation.mutate({ id, body })
    },
    [updateModelMutation]
  )

  const handleToggleEnabled = useCallback(
    (id: string, enabled: boolean): void => {
      updateModelMutation.mutate({ id, body: { enabled } })
    },
    [updateModelMutation]
  )

  const handleTestAllClick = useCallback((): void => {
    void handleTestAll()
  }, [handleTestAll])

  const handleCreateSubmit = useCallback(
    (body: Parameters<typeof gatewayApi.createModel>[0]) => {
      createMutation.mutate(body)
    },
    [createMutation]
  )

  const showEmptyOnboarding =
    !isRegisterView && !isLoading && (items?.length ?? 0) === 0 && !credentialFilter
  const filterCredential = credentialFilter ? credentialsById.get(credentialFilter) : undefined

  const credentialBanner = credentialFilter ? (
    <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-primary/20 bg-primary/5 px-3 py-2 text-sm">
      <span className="text-muted-foreground">
        按凭据筛选：
        {!filterCredential ? (
          <span className="ml-1 font-mono text-xs">{credentialFilter.slice(0, 8)}…</span>
        ) : canWrite ? (
          <Link
            to={`/gateway/credentials/${credentialFilter}`}
            className="ml-1 font-medium text-primary underline-offset-4 hover:underline"
          >
            {filterCredential.name}
          </Link>
        ) : (
          <span className="ml-1 font-medium">{filterCredential.name}</span>
        )}
      </span>
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
  ) : null

  if (isRegisterView) {
    return (
      <div className="space-y-4">
        {credentialBanner}
        <Suspense
          fallback={
            <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              加载注册表单…
            </div>
          }
        >
          <RegisterModelForm
            presets={presets ?? []}
            credentials={activeCredentials}
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
          <h3 className="text-lg font-semibold">配置团队模型供给链</h3>
          <ol className="mt-3 list-decimal space-y-2 pl-5 text-sm text-muted-foreground">
            <li>
              在{' '}
              <Link to="/gateway/credentials?tab=team" className="text-primary underline">
                凭据管理
              </Link>{' '}
              添加并启用团队凭据
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
          {canWrite ? (
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
        <div className="grid gap-4 lg:grid-cols-[minmax(280px,360px)_1fr] lg:items-start">
          <ModelInventory
            models={filteredModels}
            allModels={items ?? []}
            selectedId={selectedId}
            onSelect={handleSelect}
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
            canWrite={canWrite}
            onTestAll={handleTestAllClick}
            testingAll={testingAll}
            onRegister={!hideRegisterAction && canWrite ? goToRegister : undefined}
            onPreloadRegister={preloadRegisterModelForm}
          />
          <div className="w-full lg:sticky lg:top-6">
            <ModelInspector
              model={selectedModel}
              credentials={credentials ?? []}
              routes={routes ?? []}
              usageDays={usageDays}
              usageRow={selectedModel ? usageByRouteName.get(selectedModel.name) : undefined}
              usageLoading={usageLoading}
              isTesting={testMutation.isPending && testMutation.variables === selectedModel?.id}
              isSaving={updateModelMutation.isPending}
              onTest={handleTest}
              onSave={handleSave}
              onToggleEnabled={handleToggleEnabled}
              emptyReason={
                filteredModels.length === 0 && (items?.length ?? 0) > 0 ? 'filter' : 'none'
              }
            />
          </div>
        </div>
      )}
    </div>
  )
}
