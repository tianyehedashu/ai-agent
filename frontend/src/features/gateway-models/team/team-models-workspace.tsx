import { lazy, Suspense, useCallback, useDeferredValue, useMemo, useState } from 'react'

import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2, Plus } from 'lucide-react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'

import { gatewayApi } from '@/api/gateway'
import { Button } from '@/components/ui/button'
import {
  type HealthFilter,
  type ModelsPageView,
  type UsagePeriodDays,
  TESTABLE_CAPABILITIES,
  parseModelsPageView,
} from '@/features/gateway-models/constants'
import { useGatewayModelMutations } from '@/features/gateway-models/hooks/use-gateway-model-mutations'
import { credentialDetailHref, teamModelDetailHref } from '@/features/gateway-models/paths'
import {
  gatewayModelsListQueryKey,
  invalidateGatewayModelCaches,
  matchesHealthFilter,
  runWithConcurrency,
} from '@/features/gateway-models/utils'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useToast } from '@/hooks/use-toast'
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

const BATCH_TEST_CONCURRENCY = 3

interface TeamModelsWorkspaceProps {
  hideRegisterAction?: boolean
  /** 由父级传入时优先于 URL `view` */
  pageView?: Extract<ModelsPageView, 'list' | 'register'>
}

export function TeamModelsWorkspace({
  hideRegisterAction = false,
  pageView: pageViewProp,
}: TeamModelsWorkspaceProps): React.JSX.Element {
  const { canWrite } = useGatewayPermission()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const { toast } = useToast()
  const [searchParams, setSearchParams] = useSearchParams()
  const credentialFilter = searchParams.get('credentialId') ?? ''
  const highlightModelId = searchParams.get('modelId') ?? ''
  const pageView = pageViewProp ?? parseModelsPageView(searchParams.get('view'))
  const isRegisterView = pageView === 'register' && canWrite

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
    queryKey: gatewayModelsListQueryKey(providerFilter, credentialFilter),
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

  const needsCredentials = isRegisterView || credentialFilter !== ''

  const { data: credentials } = useQuery({
    queryKey: ['gateway', 'credentials'],
    queryFn: () => gatewayApi.listCredentials(),
    enabled: needsCredentials,
  })

  const credentialsById = useMemo(() => {
    const m = new Map<string, NonNullable<typeof credentials>[number]>()
    for (const c of credentials ?? []) {
      m.set(c.id, c)
    }
    return m
  }, [credentials])

  const filterCredential = credentialFilter ? credentialsById.get(credentialFilter) : undefined
  const registerCredentialLocked = isRegisterView && credentialFilter !== ''
  const presetProvider =
    registerCredentialLocked && filterCredential ? filterCredential.provider : providerFilter

  const { data: presets } = useQuery({
    queryKey: ['gateway', 'models', 'presets', presetProvider],
    queryFn: () =>
      presetProvider
        ? gatewayApi.listModelPresets({ provider: presetProvider })
        : gatewayApi.listModelPresets(),
    enabled: isRegisterView,
  })

  const activeCredentials = useMemo(
    () =>
      (credentials ?? []).filter(
        (c) => c.is_active || (credentialFilter !== '' && c.id === credentialFilter)
      ),
    [credentials, credentialFilter]
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

  const { createMutation } = useGatewayModelMutations({
    credentialId: credentialFilter || undefined,
    onCreateSuccess: (created) => {
      navigate(
        teamModelDetailHref(created.id, {
          credentialId: credentialFilter !== '' ? credentialFilter : undefined,
        })
      )
    },
  })

  const getModelHref = useCallback(
    (modelId: string) =>
      teamModelDetailHref(modelId, {
        credentialId: credentialFilter !== '' ? credentialFilter : undefined,
      }),
    [credentialFilter]
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

  const handleTestAll = useCallback(async (): Promise<void> => {
    const testable = (items ?? []).filter((m) => TESTABLE_CAPABILITIES.has(m.capability))
    if (testable.length === 0) return
    setTestingAll(true)
    try {
      await runWithConcurrency(testable, BATCH_TEST_CONCURRENCY, (m) => gatewayApi.testModel(m.id))
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
  }, [items, queryClient, toast, credentialFilter])

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

  const credentialBanner = credentialFilter ? (
    <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-primary/20 bg-primary/5 px-3 py-2 text-sm">
      <span className="text-muted-foreground">
        按凭据筛选：
        {!filterCredential ? (
          <span className="ml-1 font-mono text-xs">{credentialFilter.slice(0, 8)}…</span>
        ) : canWrite ? (
          <Link
            to={credentialDetailHref(credentialFilter)}
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
        <Suspense fallback={registerFormSuspenseFallback}>
          <RegisterModelForm
            presets={presets ?? []}
            credentials={activeCredentials}
            lockCredentialId={registerCredentialLocked ? credentialFilter : undefined}
            lockCredentialLabel={filterCredential?.name}
            initialProvider={filterCredential?.provider}
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
        <Suspense fallback={inventorySuspenseFallback}>
          <ModelInventory
            models={filteredModels}
            allModels={items ?? []}
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
            canWrite={canWrite}
            onTestAll={handleTestAllClick}
            testingAll={testingAll}
            onRegister={!hideRegisterAction && canWrite ? goToRegister : undefined}
            onPreloadRegister={preloadRegisterModelForm}
            onPreloadRowNavigate={preloadTeamModelDetailPane}
          />
        </Suspense>
      )}
    </div>
  )
}
