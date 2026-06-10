import { useCallback, useEffect, useMemo, useState } from 'react'

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'

import {
  gatewayApi,
  type GatewayRoute,
  type GatewayRouteCreateBody,
  type GatewayRouteUpdateBody,
} from '@/api/gateway'
import type { GatewayTeam } from '@/api/gateway/teams'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { routingStrategyLabel } from '@/features/gateway-models/constants'
import { useInfiniteGatewayModelPages } from '@/features/gateway-models/hooks/use-infinite-gateway-model-pages'
import { CreateRoutePanel } from '@/features/gateway-models/routes/create-route-panel'
import { invalidateGatewayRouteCaches } from '@/features/gateway-models/routes/query-keys'
import { RouteTopologyEditor } from '@/features/gateway-models/routes/route-topology-editor'
import type { DeploymentWeightChange } from '@/features/gateway-models/routes/use-deployment-weight-drafts'
import {
  resolveGatewayRouteTeamId,
  useVisibleGatewayRoutes,
} from '@/features/gateway-models/routes/use-visible-gateway-routes'
import { enabledGatewayModels } from '@/features/gateway-models/utils'
import { combineFetching } from '@/features/gateway-shared/combine-fetching'
import { GatewayRefreshButton } from '@/features/gateway-shared/gateway-refresh-button'
import {
  filterGatewayWritableTeams,
  isGatewayTeamWritable,
} from '@/features/gateway-teams/gateway-team-write-policy'
import {
  useGatewayMemberTeamNameMap,
  useGatewayMemberTeams,
} from '@/features/gateway-teams/use-gateway-teams'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useGatewayTeamId, useGatewayTeamRecord } from '@/hooks/use-gateway-team-id'
import { useToast } from '@/hooks/use-toast'
import { Route, Loader2, Search } from '@/lib/lucide-icons'
import { cn } from '@/lib/utils'

function canManageTeamRoutes(
  targetTeamId: string,
  memberTeams: readonly GatewayTeam[],
  isPlatformAdmin: boolean,
  isPlatformViewer: boolean
): boolean {
  if (isPlatformViewer) return false
  if (isPlatformAdmin) return true
  const team = memberTeams.find((item) => item.id === targetTeamId)
  return team ? isGatewayTeamWritable(team, false) : false
}

function routeTeamLabel(
  route: GatewayRoute,
  teamNameById: ReadonlyMap<string, string>
): string | null {
  if (route.source === 'system') return '系统'
  const ownerTeamId = resolveGatewayRouteTeamId(route)
  if (!ownerTeamId) return null
  return teamNameById.get(ownerTeamId) ?? ownerTeamId.slice(0, 8)
}

export function RouteWorkspace(): React.JSX.Element {
  const workspaceTeamId = useGatewayTeamId()
  const queryClient = useQueryClient()
  const { isPlatformAdmin, isPlatformViewer } = useGatewayPermission()
  const currentTeam = useGatewayTeamRecord(workspaceTeamId)
  const { data: memberTeams = [] } = useGatewayMemberTeams()
  const teamNameById = useGatewayMemberTeamNameMap()
  const createTeamOptions = useMemo(
    () => filterGatewayWritableTeams(memberTeams, isPlatformAdmin, isPlatformViewer),
    [memberTeams, isPlatformAdmin, isPlatformViewer]
  )
  const defaultCreateTeamId = useMemo(() => {
    if (createTeamOptions.some((team) => team.id === workspaceTeamId)) return workspaceTeamId
    return createTeamOptions[0]?.id ?? ''
  }, [createTeamOptions, workspaceTeamId])
  const canCreateRoutes = createTeamOptions.length > 0
  const { toast } = useToast()
  const [searchParams, setSearchParams] = useSearchParams()
  const routeIdFromUrl = searchParams.get('routeId') ?? ''

  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [createMode, setCreateMode] = useState(false)
  const [createFormKey, setCreateFormKey] = useState(0)
  const [createTeamId, setCreateTeamId] = useState(defaultCreateTeamId)
  const modelsLinkTeamId = createMode && createTeamId ? createTeamId : workspaceTeamId
  const modelsLinkTeam =
    memberTeams.find((team) => team.id === modelsLinkTeamId) ??
    (modelsLinkTeamId === workspaceTeamId ? currentTeam : null)
  const modelsHref =
    modelsLinkTeam?.kind === 'personal'
      ? `/gateway/teams/${modelsLinkTeamId}/models?tab=personal`
      : `/gateway/teams/${modelsLinkTeamId}/models?tab=shared`

  const {
    routes,
    isLoading,
    isFetching: routesFetching,
    isError: routesError,
    error: routesQueryError,
    refetch: refetchRoutes,
  } = useVisibleGatewayRoutes()

  const selectedRoute = useMemo(
    () => routes.find((route) => route.id === selectedId) ?? null,
    [routes, selectedId]
  )

  useEffect(() => {
    if (createTeamOptions.length === 0) {
      if (createTeamId.length > 0) setCreateTeamId('')
      return
    }
    if (createTeamOptions.some((team) => team.id === createTeamId)) return
    setCreateTeamId(defaultCreateTeamId)
  }, [createTeamOptions, createTeamId, defaultCreateTeamId])

  const activeTeamId = useMemo(() => {
    if (createMode) return createTeamId
    const ownerTeamId = selectedRoute ? resolveGatewayRouteTeamId(selectedRoute) : null
    return ownerTeamId ?? workspaceTeamId
  }, [createMode, createTeamId, selectedRoute, workspaceTeamId])

  const needsRouteModels = (createMode && createTeamId.length > 0) || selectedId !== null

  const {
    items: models,
    isLoading: modelsLoading,
    isFetching: modelsFetching,
    refetch: refetchModels,
  } = useInfiniteGatewayModelPages(
    activeTeamId,
    { registry_scope: 'callable' },
    { enabled: needsRouteModels, prefetchMode: 'idle' }
  )

  const pickerModels = useMemo(() => enabledGatewayModels(models), [models])

  const selectedRouteEditable =
    selectedRoute !== null &&
    selectedRoute.source !== 'system' &&
    (() => {
      const ownerTeamId = resolveGatewayRouteTeamId(selectedRoute)
      return ownerTeamId
        ? canManageTeamRoutes(ownerTeamId, memberTeams, isPlatformAdmin, isPlatformViewer)
        : false
    })()

  const selectedRouteTeamLabel = selectedRoute ? routeTeamLabel(selectedRoute, teamNameById) : null
  const createTeamLabel = createTeamId
    ? (teamNameById.get(createTeamId) ?? createTeamId.slice(0, 8))
    : null

  useEffect(() => {
    if (!routeIdFromUrl || routes.length === 0) return
    if (routes.some((route) => route.id === routeIdFromUrl)) {
      setSelectedId(routeIdFromUrl)
      setCreateMode(false)
    }
  }, [routeIdFromUrl, routes])

  useEffect(() => {
    if (selectedId && !routes.some((route) => route.id === selectedId)) {
      setSelectedId(null)
    }
  }, [routes, selectedId])

  const filteredRoutes = useMemo(() => {
    const q = search.trim().toLowerCase()
    return routes.filter((route) => {
      if (!q) return true
      const routeTeamId = resolveGatewayRouteTeamId(route)
      const teamName = routeTeamId ? (teamNameById.get(routeTeamId) ?? '') : ''
      return (
        route.virtual_model.toLowerCase().includes(q) ||
        route.primary_models.some((name) => name.toLowerCase().includes(q)) ||
        teamName.toLowerCase().includes(q)
      )
    })
  }, [routes, search, teamNameById])

  /** 权重属于模型（deployment）；保存/创建路由时将草稿变更解析为模型 ID 一并提交 */
  const resolveWeightUpdates = useCallback(
    (weightChanges: readonly DeploymentWeightChange[]): { modelId: string; weight: number }[] =>
      weightChanges.flatMap((change) => {
        const target = models.find((m) => m.name === change.modelName)
        return target && target.weight !== change.weight
          ? [{ modelId: target.id, weight: change.weight }]
          : []
      }),
    [models]
  )

  const applyWeightUpdates = useCallback(
    async (
      teamId: string,
      weightUpdates: readonly { modelId: string; weight: number }[]
    ): Promise<void> => {
      await Promise.all(
        weightUpdates.map((update) =>
          gatewayApi.updateModel(teamId, update.modelId, { weight: update.weight })
        )
      )
    },
    []
  )

  const createMutation = useMutation({
    mutationFn: async ({
      teamId,
      body,
      weightUpdates,
    }: {
      teamId: string
      body: GatewayRouteCreateBody
      weightUpdates: readonly { modelId: string; weight: number }[]
    }) => {
      await applyWeightUpdates(teamId, weightUpdates)
      return gatewayApi.createRoute(teamId, body)
    },
    onSuccess: (created) => {
      invalidateGatewayRouteCaches(queryClient)
      void refetchModels()
      setCreateMode(false)
      setSelectedId(created.id)
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev)
          next.set('routeId', created.id)
          return next
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
    mutationFn: async ({
      teamId,
      id,
      body,
      weightUpdates,
    }: {
      teamId: string
      id: string
      body: GatewayRouteUpdateBody
      weightUpdates: readonly { modelId: string; weight: number }[]
    }) => {
      await applyWeightUpdates(teamId, weightUpdates)
      await gatewayApi.updateRoute(teamId, id, body)
    },
    onSuccess: () => {
      invalidateGatewayRouteCaches(queryClient)
      void refetchModels()
      toast({ title: '路由已更新' })
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '更新失败', description: e.message })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: ({ teamId, id }: { teamId: string; id: string }) =>
      gatewayApi.deleteRoute(teamId, id),
    onSuccess: () => {
      invalidateGatewayRouteCaches(queryClient)
      setSelectedId(null)
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev)
          next.delete('routeId')
          return next
        },
        { replace: true }
      )
      toast({ title: '路由已删除' })
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '删除失败', description: e.message })
    },
  })

  function selectRoute(id: string): void {
    setCreateMode(false)
    setSelectedId(id)
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        next.set('routeId', id)
        return next
      },
      { replace: true }
    )
  }

  function startCreate(): void {
    setCreateTeamId(defaultCreateTeamId)
    setCreateMode(true)
    setCreateFormKey((k) => k + 1)
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        next.delete('routeId')
        return next
      },
      { replace: true }
    )
  }

  function cancelCreate(): void {
    setCreateMode(false)
  }

  function changeCreateTeam(teamId: string): void {
    setCreateTeamId(teamId)
  }

  function handleSave(
    route: GatewayRoute,
    body: GatewayRouteUpdateBody,
    weightChanges: readonly DeploymentWeightChange[]
  ): void {
    const ownerTeamId = resolveGatewayRouteTeamId(route)
    if (!ownerTeamId) return
    updateMutation.mutate({
      teamId: ownerTeamId,
      id: route.id,
      body,
      weightUpdates: resolveWeightUpdates(weightChanges),
    })
  }

  function handleDelete(route: GatewayRoute): void {
    const ownerTeamId = resolveGatewayRouteTeamId(route)
    if (!ownerTeamId) return
    deleteMutation.mutate({ teamId: ownerTeamId, id: route.id })
  }

  const searchActive = search.trim().length > 0

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="max-w-xl text-sm text-muted-foreground">
          虚拟路由定义客户端请求的 <span className="font-mono">model</span> 名与主模型池、Fallback
          及 Router 策略。需先在{' '}
          <Link to={modelsHref} className="text-primary underline-offset-4 hover:underline">
            模型管理
          </Link>{' '}
          配置供给。
        </p>
        {canCreateRoutes ? (
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
                  placeholder="搜索虚拟名、主模型、团队…"
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
            ) : routesError ? (
              <p className="px-3 py-12 text-center text-sm text-destructive">
                加载失败：
                {routesQueryError instanceof Error ? routesQueryError.message : '请稍后重试'}
              </p>
            ) : filteredRoutes.length === 0 ? (
              <p className="px-3 py-12 text-center text-sm text-muted-foreground">
                {searchActive ? `暂无匹配「${search.trim()}」的路由` : '暂无虚拟路由'}
              </p>
            ) : (
              <ul className="divide-y">
                {filteredRoutes.map((route) => {
                  const teamLabel = routeTeamLabel(route, teamNameById)
                  return (
                    <li key={route.id}>
                      <button
                        type="button"
                        className={cn(
                          'w-full px-3 py-2.5 text-left hover:bg-muted/40',
                          !createMode && route.id === selectedId && 'bg-primary/10'
                        )}
                        onClick={() => {
                          selectRoute(route.id)
                        }}
                      >
                        <p className="flex min-w-0 items-center gap-2 font-mono text-sm font-medium">
                          <span className="min-w-0 truncate">{route.virtual_model}</span>
                          {teamLabel ? (
                            <span className="shrink-0 rounded bg-muted px-1.5 py-0.5 font-sans text-[10px] font-normal text-muted-foreground">
                              {teamLabel}
                            </span>
                          ) : null}
                        </p>
                        <p className="mt-0.5 truncate text-xs text-muted-foreground">
                          {routingStrategyLabel(route.strategy)} ·{' '}
                          {route.primary_models.join(', ') || '—'}
                        </p>
                        {!route.enabled ? (
                          <p className="mt-1 text-xs text-amber-600">已禁用</p>
                        ) : null}
                      </button>
                    </li>
                  )
                })}
              </ul>
            )}
          </ScrollArea>
        </div>

        {createMode ? (
          <CreateRoutePanel
            key={createFormKey}
            targetTeamId={createTeamId}
            targetTeamLabel={createTeamLabel}
            targetTeams={createTeamOptions}
            onTargetTeamChange={changeCreateTeam}
            pickerModels={pickerModels}
            modelsLoading={modelsLoading}
            onSubmit={(body, weightChanges) => {
              if (!createTeamId) {
                toast({ variant: 'destructive', title: '请选择所属团队' })
                return
              }
              createMutation.mutate({
                teamId: createTeamId,
                body,
                weightUpdates: resolveWeightUpdates(weightChanges),
              })
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
            modelsLoading={modelsLoading}
            teamLabel={selectedRouteTeamLabel}
            readOnly={selectedRoute !== null && !selectedRouteEditable}
            onSave={(_id, body, weightChanges) => {
              if (!selectedRoute) return
              handleSave(selectedRoute, body, weightChanges)
            }}
            onDelete={() => {
              if (!selectedRoute) return
              handleDelete(selectedRoute)
            }}
          />
        )}
      </div>
    </div>
  )
}
