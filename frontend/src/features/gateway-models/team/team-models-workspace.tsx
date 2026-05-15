import { useCallback, useEffect, useMemo, useState } from 'react'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'

import { gatewayApi, type GatewayModelUpdateBody } from '@/api/gateway'
import { Button } from '@/components/ui/button'
import { type HealthFilter, TESTABLE_CAPABILITIES } from '@/features/gateway-models/constants'
import { matchesHealthFilter } from '@/features/gateway-models/utils'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useToast } from '@/hooks/use-toast'
import { MODEL_PROVIDERS } from '@/types/user-model'

import { ModelHealthStrip } from './model-health-strip'
import { ModelInspector } from './model-inspector'
import { ModelInventory } from './model-inventory'
import { RegisterModelWizard } from './register-model-wizard'

interface TeamModelsWorkspaceProps {
  /** 深链选中模型 id（/gateway/models/:modelId 或 query） */
  initialModelId?: string
}

export function TeamModelsWorkspace({
  initialModelId,
}: TeamModelsWorkspaceProps): React.JSX.Element {
  const { canWrite } = useGatewayPermission()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [searchParams, setSearchParams] = useSearchParams()
  const credentialFilter = searchParams.get('credentialId') ?? ''
  const highlightModelId = searchParams.get('modelId') ?? initialModelId ?? ''

  const [wizardOpen, setWizardOpen] = useState(false)
  const [selectedId, setSelectedId] = useState<string | null>(initialModelId ?? null)
  const [providerFilter, setProviderFilter] = useState('')
  const [search, setSearch] = useState('')
  const [usageDays, setUsageDays] = useState<1 | 7 | 30>(7)
  const [healthFilter, setHealthFilter] = useState<HealthFilter>('all')
  const [testingAll, setTestingAll] = useState(false)
  const [providerChoices, setProviderChoices] = useState<string[]>(() =>
    MODEL_PROVIDERS.map((p) => p.id)
  )

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
  })

  const { data: routes } = useQuery({
    queryKey: ['gateway', 'routes'],
    queryFn: () => gatewayApi.listRoutes(),
  })

  const { data: presets } = useQuery({
    queryKey: ['gateway', 'models', 'presets', providerFilter],
    queryFn: () =>
      providerFilter
        ? gatewayApi.listModelPresets({ provider: providerFilter })
        : gatewayApi.listModelPresets(),
  })

  const { data: credentials } = useQuery({
    queryKey: ['gateway', 'credentials'],
    queryFn: () => gatewayApi.listCredentials(),
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

  useEffect(() => {
    if (providerFilter !== '' || !items?.length) return
    const s = new Set<string>(MODEL_PROVIDERS.map((p) => p.id))
    for (const m of items) {
      s.add(m.provider)
    }
    setProviderChoices(Array.from(s).sort())
  }, [items, providerFilter])

  useEffect(() => {
    if (!initialModelId || !items?.length) return
    const found = items.some((m) => m.id === initialModelId)
    if (found) setSelectedId(initialModelId)
  }, [initialModelId, items])

  const filteredModels = useMemo(() => {
    const q = search.trim().toLowerCase()
    return (items ?? []).filter((m) => {
      if (!matchesHealthFilter(m, healthFilter)) return false
      if (!q) return true
      return (
        m.name.toLowerCase().includes(q) ||
        m.real_model.toLowerCase().includes(q) ||
        m.provider.toLowerCase().includes(q)
      )
    })
  }, [items, healthFilter, search])

  const selectedModel = useMemo(
    () => (items ?? []).find((m) => m.id === selectedId) ?? null,
    [items, selectedId]
  )

  const createMutation = useMutation({
    mutationFn: gatewayApi.createModel,
    onSuccess: (created) => {
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'models'] })
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'models', 'usage-summary'] })
      setWizardOpen(false)
      setSelectedId(created.id)
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

  async function handleTestAll(): Promise<void> {
    const testable = (items ?? []).filter((m) => TESTABLE_CAPABILITIES.has(m.capability))
    if (testable.length === 0) return
    setTestingAll(true)
    try {
      for (const m of testable) {
        await gatewayApi.testModel(m.id)
      }
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'models'] })
      toast({ title: '批量测试完成' })
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      toast({ variant: 'destructive', title: '批量测试中断', description: msg })
    } finally {
      setTestingAll(false)
    }
  }

  const showEmptyOnboarding = !isLoading && (items?.length ?? 0) === 0 && !credentialFilter

  return (
    <div className="space-y-4">
      {credentialFilter ? (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-primary/20 bg-primary/5 px-3 py-2 text-sm">
          <span className="text-muted-foreground">
            按凭据筛选：
            {(() => {
              const fc = credentialsById.get(credentialFilter)
              if (!fc) {
                return (
                  <span className="ml-1 font-mono text-xs">{credentialFilter.slice(0, 8)}…</span>
                )
              }
              return canWrite ? (
                <Link
                  to={`/gateway/credentials/${credentialFilter}`}
                  className="ml-1 font-medium text-primary underline-offset-4 hover:underline"
                >
                  {fc.name}
                </Link>
              ) : (
                <span className="ml-1 font-medium">{fc.name}</span>
              )
            })()}
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
      ) : null}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-muted-foreground">用量区间</span>
          <div className="flex gap-1 rounded-md border bg-background p-0.5">
            {([1, 7, 30] as const).map((d) => (
              <Button
                key={d}
                size="sm"
                variant={usageDays === d ? 'default' : 'ghost'}
                className="h-7 px-2 text-xs"
                type="button"
                onClick={() => {
                  setUsageDays(d)
                }}
              >
                {d === 1 ? '24h' : d === 7 ? '7d' : '30d'}
              </Button>
            ))}
          </div>
        </div>
        {canWrite ? (
          <Button
            size="sm"
            onClick={() => {
              setWizardOpen(true)
            }}
          >
            <Plus className="mr-1.5 h-4 w-4" />
            注册模型
          </Button>
        ) : null}
      </div>

      {!showEmptyOnboarding && (items?.length ?? 0) > 0 ? (
        <ModelHealthStrip
          models={items ?? []}
          healthFilter={healthFilter}
          onHealthFilterChange={setHealthFilter}
          canWrite={canWrite}
          onTestAll={() => void handleTestAll()}
          testingAll={testingAll}
        />
      ) : null}

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
              onClick={() => {
                setWizardOpen(true)
              }}
            >
              <Plus className="mr-1.5 h-4 w-4" />
              注册第一个模型
            </Button>
          ) : null}
        </div>
      ) : (
        <div className="grid min-h-[480px] gap-4 lg:grid-cols-[minmax(280px,360px)_1fr]">
          <ModelInventory
            models={filteredModels}
            selectedId={selectedId}
            onSelect={setSelectedId}
            isLoading={isLoading}
            search={search}
            onSearchChange={setSearch}
            providerFilter={providerFilter}
            onProviderFilterChange={setProviderFilter}
            providerChoices={providerChoices}
            usageDays={usageDays}
            usageByRouteName={usageByRouteName}
            usageLoading={usageLoading}
            highlightModelId={highlightModelId || undefined}
          />
          <ModelInspector
            model={selectedModel}
            credentials={credentials ?? []}
            routes={routes ?? []}
            usageDays={usageDays}
            usageRow={selectedModel ? usageByRouteName.get(selectedModel.name) : undefined}
            usageLoading={usageLoading}
            isTesting={testMutation.isPending && testMutation.variables === selectedModel?.id}
            isSaving={updateModelMutation.isPending}
            onTest={(id) => {
              testMutation.mutate(id)
            }}
            onSave={(id, body) => {
              updateModelMutation.mutate({ id, body })
            }}
            onToggleEnabled={(id, enabled) => {
              updateModelMutation.mutate({ id, body: { enabled } })
            }}
          />
        </div>
      )}

      <RegisterModelWizard
        open={wizardOpen}
        onOpenChange={setWizardOpen}
        presets={presets ?? []}
        credentials={activeCredentials}
        onSubmit={(body) => {
          createMutation.mutate(body)
        }}
        isSubmitting={createMutation.isPending}
      />
    </div>
  )
}
