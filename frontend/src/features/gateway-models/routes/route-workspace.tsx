import { useEffect, useMemo, useState } from 'react'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'

import { gatewayApi, type GatewayRouteUpdateBody } from '@/api/gateway'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { routingStrategyLabel } from '@/features/gateway-models/constants'
import { useInfiniteGatewayModelPages } from '@/features/gateway-models/hooks/use-infinite-gateway-model-pages'
import { CreateRoutePanel } from '@/features/gateway-models/routes/create-route-panel'
import { RouteTopologyEditor } from '@/features/gateway-models/routes/route-topology-editor'
import { enabledGatewayModels, GATEWAY_MODELS_STALE_MS } from '@/features/gateway-models/utils'
import { combineFetching } from '@/features/gateway-shared/combine-fetching'
import { GatewayRefreshButton } from '@/features/gateway-shared/gateway-refresh-button'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useGatewayTeamId, useGatewayTeamRecord } from '@/hooks/use-gateway-team-id'
import { useToast } from '@/hooks/use-toast'
import { Route, Loader2, Search } from '@/lib/lucide-icons'
import { cn } from '@/lib/utils'

export function RouteWorkspace(): React.JSX.Element {
  const teamId = useGatewayTeamId()
  const { canWrite } = useGatewayPermission()
  const currentTeam = useGatewayTeamRecord(teamId)
  const isPersonalTeam = currentTeam?.kind === 'personal'
  const modelsHref = isPersonalTeam
    ? `/gateway/teams/${teamId}/models?tab=personal`
    : `/gateway/teams/${teamId}/models?tab=shared`
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [searchParams, setSearchParams] = useSearchParams()
  const routeIdFromUrl = searchParams.get('routeId') ?? ''

  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [createMode, setCreateMode] = useState(false)
  const [createFormKey, setCreateFormKey] = useState(0)

  const {
    data: routes,
    isLoading,
    isFetching: routesFetching,
    refetch: refetchRoutes,
  } = useQuery({
    queryKey: ['gateway', 'routes', teamId],
    queryFn: () => gatewayApi.listRoutes(teamId),
    staleTime: GATEWAY_MODELS_STALE_MS,
  })

  const needsRouteModels = createMode || selectedId !== null

  const {
    items: models,
    isLoading: modelsLoading,
    isFetching: modelsFetching,
    refetch: refetchModels,
  } = useInfiniteGatewayModelPages(
    teamId,
    { registry_scope: 'callable' },
    { enabled: needsRouteModels, prefetchMode: 'idle' }
  )

  const pickerModels = useMemo(() => enabledGatewayModels(models), [models])

  useEffect(() => {
    if (!routeIdFromUrl || !routes?.length) return
    if (routes.some((r) => r.id === routeIdFromUrl)) {
      setSelectedId(routeIdFromUrl)
      setCreateMode(false)
    }
  }, [routeIdFromUrl, routes])

  const filteredRoutes = useMemo(() => {
    const q = search.trim().toLowerCase()
    return (routes ?? []).filter((r) => {
      if (!q) return true
      return (
        r.virtual_model.toLowerCase().includes(q) ||
        r.primary_models.some((m) => m.toLowerCase().includes(q))
      )
    })
  }, [routes, search])

  const selectedRoute = useMemo(
    () => (routes ?? []).find((r) => r.id === selectedId) ?? null,
    [routes, selectedId]
  )

  const createMutation = useMutation({
    mutationFn: (body: Parameters<typeof gatewayApi.createRoute>[1]) =>
      gatewayApi.createRoute(teamId, body),
    onSuccess: (created) => {
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'routes'] })
      setCreateMode(false)
      setSelectedId(created.id)
      setSearchParams(
        (prev) => {
          const n = new URLSearchParams(prev)
          n.set('routeId', created.id)
          return n
        },
        { replace: true }
      )
      toast({ title: '路由已创建' })
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '创建失败', description: e.message })
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: GatewayRouteUpdateBody }) =>
      gatewayApi.updateRoute(teamId, id, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'routes'] })
      toast({ title: '路由已更新' })
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '更新失败', description: e.message })
    },
  })

  function selectRoute(id: string): void {
    setCreateMode(false)
    setSelectedId(id)
    setSearchParams(
      (prev) => {
        const n = new URLSearchParams(prev)
        n.set('routeId', id)
        return n
      },
      { replace: true }
    )
  }

  function startCreate(): void {
    setCreateMode(true)
    setCreateFormKey((k) => k + 1)
    setSearchParams(
      (prev) => {
        const n = new URLSearchParams(prev)
        n.delete('routeId')
        return n
      },
      { replace: true }
    )
  }

  function cancelCreate(): void {
    setCreateMode(false)
  }

  const deleteMutation = useMutation({
    mutationFn: (id: string) => gatewayApi.deleteRoute(teamId, id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'routes'] })
      setSelectedId(null)
      setSearchParams(
        (prev) => {
          const n = new URLSearchParams(prev)
          n.delete('routeId')
          return n
        },
        { replace: true }
      )
      toast({ title: '路由已删除' })
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '删除失败', description: e.message })
    },
  })

  const teamCustomRoutes = useMemo(
    () => (routes ?? []).filter((r) => r.source !== 'system'),
    [routes]
  )

  return (
    <div className="space-y-4">
      {currentTeam ? (
        <div className="rounded-md border border-border/60 bg-muted/20 px-3 py-2 text-sm text-muted-foreground">
          {isPersonalTeam ? (
            <>个人工作区 · 模型池来自个人注册别名</>
          ) : (
            <>
              当前团队：<span className="font-medium text-foreground">{currentTeam.name}</span> ·
              模型池来自团队注册别名
            </>
          )}
        </div>
      ) : null}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="max-w-xl text-sm text-muted-foreground">
          虚拟路由定义客户端请求的 <span className="font-mono">model</span> 名与主模型池、Fallback
          及 Router 策略。需先在{' '}
          <Link to={modelsHref} className="text-primary underline-offset-4 hover:underline">
            模型管理
          </Link>{' '}
          配置供给。
        </p>
        {canWrite ? (
          <Button
            size="sm"
            variant={createMode ? 'secondary' : 'default'}
            onClick={() => {
              startCreate()
            }}
          >
            <Route className="mr-1.5 h-4 w-4" />
            新建虚拟路由
          </Button>
        ) : null}
      </div>

      <div className="grid min-h-[480px] gap-4 lg:grid-cols-[minmax(260px,320px)_1fr]">
        <div className="flex min-h-0 flex-col rounded-lg border bg-card">
          <div className="border-b p-3">
            <div className="flex items-center gap-2">
              <div className="relative min-w-0 flex-1">
                <Search className="pointer-events-none absolute left-2.5 top-2 h-4 w-4 text-muted-foreground" />
                <Input
                  value={search}
                  onChange={(e) => {
                    setSearch(e.target.value)
                  }}
                  placeholder="搜索虚拟名…"
                  className="h-8 pl-8 text-sm"
                />
              </div>
              <GatewayRefreshButton
                isFetching={combineFetching(
                  routesFetching,
                  needsRouteModels ? modelsFetching : false
                )}
                ariaLabel="刷新虚拟路由"
                onRefresh={() => {
                  const tasks: Promise<unknown>[] = [refetchRoutes()]
                  if (needsRouteModels) tasks.push(refetchModels())
                  void Promise.all(tasks)
                }}
              />
            </div>
          </div>
          <ScrollArea className="min-h-[280px] flex-1">
            {isLoading ? (
              <div className="flex justify-center py-12">
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
              </div>
            ) : filteredRoutes.length === 0 ? (
              <p className="px-3 py-12 text-center text-sm text-muted-foreground">
                {teamCustomRoutes.length === 0
                  ? '暂无团队自定义路由；系统路由见下方（只读）'
                  : '暂无匹配的路由'}
              </p>
            ) : (
              <ul className="divide-y">
                {filteredRoutes.map((r) => (
                  <li key={r.id}>
                    <button
                      type="button"
                      className={cn(
                        'w-full px-3 py-2.5 text-left hover:bg-muted/40',
                        !createMode && r.id === selectedId && 'bg-primary/10'
                      )}
                      onClick={() => {
                        selectRoute(r.id)
                      }}
                    >
                      <p className="flex items-center gap-2 font-mono text-sm font-medium">
                        {r.virtual_model}
                        {r.source === 'system' ? (
                          <span className="rounded bg-muted px-1.5 py-0.5 font-sans text-[10px] font-normal text-muted-foreground">
                            系统
                          </span>
                        ) : null}
                      </p>
                      <p className="mt-0.5 truncate text-xs text-muted-foreground">
                        {routingStrategyLabel(r.strategy)} · {r.primary_models.join(', ') || '—'}
                      </p>
                      {!r.enabled ? <p className="mt-1 text-xs text-amber-600">已禁用</p> : null}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </ScrollArea>
        </div>

        {createMode ? (
          <CreateRoutePanel
            key={createFormKey}
            pickerModels={pickerModels}
            modelsLoading={modelsLoading}
            onSubmit={(body) => {
              createMutation.mutate(body)
            }}
            onCancel={cancelCreate}
            isSubmitting={createMutation.isPending}
          />
        ) : (
          <RouteTopologyEditor
            route={selectedRoute}
            models={models}
            pickerModels={pickerModels}
            isSaving={updateMutation.isPending}
            isDeleting={deleteMutation.isPending}
            onSave={(id, body) => {
              updateMutation.mutate({ id, body })
            }}
            onDelete={(id) => {
              deleteMutation.mutate(id)
            }}
          />
        )}
      </div>
    </div>
  )
}
