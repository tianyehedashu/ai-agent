import { memo, useCallback, useEffect, useMemo, useState } from 'react'

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'

import { gatewayApi } from '@/api/gateway'
import type {
  GatewayRoute,
  GatewayRouteCreateBody,
  GatewayRouteUpdateBody,
} from '@/api/gateway/routes'
import type { GatewayTeam } from '@/api/gateway/teams'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { routingStrategyLabel } from '@/features/gateway-models/constants'
import { useInfiniteGatewayModelPages } from '@/features/gateway-models/hooks/use-infinite-gateway-model-pages'
import { modelsIndexHref } from '@/features/gateway-models/paths'
import { CreateRoutePanel } from '@/features/gateway-models/routes/create-route-panel'
import { invalidateGatewayRouteCaches } from '@/features/gateway-models/routes/query-keys'
import { RouteSharePanel } from '@/features/gateway-models/routes/route-share-panel'
import { RouteTopologyEditor } from '@/features/gateway-models/routes/route-topology-editor'
import { SharedRoutesPanel } from '@/features/gateway-models/routes/shared-routes-panel'
import type { DeploymentWeightChange } from '@/features/gateway-models/routes/use-deployment-weight-drafts'
import { usePersonalRouteCallableModels } from '@/features/gateway-models/routes/use-personal-route-callable-models'
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

function isPersonalTeamId(teamId: string, memberTeams: readonly GatewayTeam[]): boolean {
  return memberTeams.some((team) => team.id === teamId && team.kind === 'personal')
}

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

interface RouteSidebarItemProps {
  route: GatewayRoute
  teamLabel: string | null
  selected: boolean
  createMode: boolean
  onSelect: (id: string) => void
}

const RouteSidebarItem = memo(function RouteSidebarItem({
  route,
  teamLabel,
  selected,
  createMode,
  onSelect,
}: RouteSidebarItemProps): React.JSX.Element {
  return (
    <li>
      <button
        type="button"
        className={cn(
          'w-full px-3 py-2.5 text-left hover:bg-muted/40',
          !createMode && selected && 'bg-primary/10'
        )}
        onClick={() => {
          onSelect(route.id)
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
          {routingStrategyLabel(route.strategy)} · {route.primary_models.join(', ') || '—'}
        </p>
        {!route.enabled ? <p className="mt-1 text-xs text-amber-600">已禁用</p> : null}
      </button>
    </li>
  )
})

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
  const personalTeamId = useMemo(
    () => memberTeams.find((team) => team.kind === 'personal')?.id ?? '',
    [memberTeams]
  )
  const defaultCreateTeamId = useMemo(() => {
    if (personalTeamId && createTeamOptions.some((team) => team.id === personalTeamId)) {
      return personalTeamId
    }
    if (createTeamOptions.some((team) => team.id === workspaceTeamId)) return workspaceTeamId
    return createTeamOptions[0]?.id ?? ''
  }, [createTeamOptions, personalTeamId, workspaceTeamId])
  const canCreateRoutes = createTeamOptions.length > 0
  const { toast } = useToast()
  const [searchParams, setSearchParams] = useSearchParams()
  const routeIdFromUrl = searchParams.get('routeId') ?? ''
  const scopeFilter = searchParams.get('scope') ?? 'all'

  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [createMode, setCreateMode] = useState(false)
  const [createFormKey, setCreateFormKey] = useState(0)
  const [createTeamId, setCreateTeamId] = useState(defaultCreateTeamId)
  const modelsLinkTeamId = createMode && createTeamId ? createTeamId : workspaceTeamId
  const modelsLinkTeam =
    memberTeams.find((team) => team.id === modelsLinkTeamId) ??
    (modelsLinkTeamId === workspaceTeamId ? currentTeam : null)
  const modelsHref = modelsIndexHref(modelsLinkTeamId, {
    scope: modelsLinkTeam?.kind === 'personal' ? 'personal' : 'team',
  })

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

  const isPersonalRouteContext = useMemo(
    () => isPersonalTeamId(activeTeamId, memberTeams),
    [activeTeamId, memberTeams]
  )

  const {
    items: teamModels,
    isLoading: teamModelsLoading,
    isFetching: teamModelsFetching,
    refetch: refetchTeamModels,
  } = useInfiniteGatewayModelPages(
    activeTeamId,
    { registry_scope: 'callable' },
    { enabled: needsRouteModels && !isPersonalRouteContext, prefetchMode: 'idle' }
  )

  const {
    items: personalCallableItems,
    isLoading: personalModelsLoading,
    isFetching: personalModelsFetching,
    refetch: refetchPersonalModels,
  } = usePersonalRouteCallableModels({
    enabled: needsRouteModels && isPersonalRouteContext,
  })

  const models = isPersonalRouteContext ? personalCallableItems : teamModels
  const modelsLoading = isPersonalRouteContext ? personalModelsLoading : teamModelsLoading
  const modelsFetching = isPersonalRouteContext ? personalModelsFetching : teamModelsFetching
  const refetchModels = isPersonalRouteContext ? refetchPersonalModels : refetchTeamModels

  const pickerModels = useMemo(() => enabledGatewayModels(models), [models])
  const modelsByName = useMemo(() => new Map(models.map((model) => [model.name, model])), [models])
  const memberTeamById = useMemo(
    () => new Map(memberTeams.map((team) => [team.id, team])),
    [memberTeams]
  )

  const selectedRouteEditable = useMemo(() => {
    if (selectedRoute === null || selectedRoute.source === 'system') return false
    const ownerTeamId = resolveGatewayRouteTeamId(selectedRoute)
    if (!ownerTeamId) return false
    return canManageTeamRoutes(ownerTeamId, memberTeams, isPlatformAdmin, isPlatformViewer)
  }, [selectedRoute, memberTeams, isPlatformAdmin, isPlatformViewer])

  const workspaceTeamIsShared = Boolean(currentTeam) && currentTeam?.kind !== 'personal'
  const canManageWorkspaceTeam = useMemo(
    () => canManageTeamRoutes(workspaceTeamId, memberTeams, isPlatformAdmin, isPlatformViewer),
    [workspaceTeamId, memberTeams, isPlatformAdmin, isPlatformViewer]
  )

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
      const routeTeamId = resolveGatewayRouteTeamId(route)
      const team = routeTeamId ? memberTeamById.get(routeTeamId) : undefined
      if (scopeFilter === 'personal' && team?.kind !== 'personal') return false
      if (scopeFilter === 'shared' && team?.kind === 'personal') return false
      if (!q) return true
      const teamName = routeTeamId ? (teamNameById.get(routeTeamId) ?? '') : ''
      return (
        route.virtual_model.toLowerCase().includes(q) ||
        route.primary_models.some((name) => name.toLowerCase().includes(q)) ||
        teamName.toLowerCase().includes(q)
      )
    })
  }, [routes, search, teamNameById, scopeFilter, memberTeamById])

  const resolveWeightUpdates = useCallback(
    (
      weightChanges: readonly DeploymentWeightChange[]
    ): { teamId: string; modelId: string; weight: number }[] =>
      weightChanges.flatMap((change) => {
        const target = modelsByName.get(change.modelName)
        if (!target) return []
        const ownerTeamId = target.tenant_id ?? target.team_id ?? activeTeamId
        if (!ownerTeamId) return []
        return target.weight !== change.weight
          ? [{ teamId: ownerTeamId, modelId: target.id, weight: change.weight }]
          : []
      }),
    [modelsByName, activeTeamId]
  )

  const applyWeightUpdates = useCallback(
    async (weightUpdates: readonly { teamId: string; modelId: string; weight: number }[]) => {
      await Promise.all(
        weightUpdates.map((update) =>
          gatewayApi.updateModel(update.teamId, update.modelId, { weight: update.weight })
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
      weightUpdates: readonly { teamId: string; modelId: string; weight: number }[]
    }) => {
      await applyWeightUpdates(weightUpdates)
      if (isPersonalTeamId(teamId, memberTeams)) {
        return gatewayApi.createMyRoute(body)
      }
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
      weightUpdates: readonly { teamId: string; modelId: string; weight: number }[]
    }) => {
      await applyWeightUpdates(weightUpdates)
      if (isPersonalTeamId(teamId, memberTeams)) {
        await gatewayApi.updateMyRoute(id, body)
        return
      }
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
      isPersonalTeamId(teamId, memberTeams)
        ? gatewayApi.deleteMyRoute(id)
        : gatewayApi.deleteRoute(teamId, id),
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

  const allowCreatePersonalBatchAdd = isPersonalTeamId(createTeamId, memberTeams)

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

  useEffect(() => {
    if (searchParams.get('create') === '1' && canCreateRoutes) {
      startCreate()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- 仅 URL 深链触发一次
  }, [])

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
            <div className="mb-2">
              <Select
                value={scopeFilter}
                onValueChange={(value) => {
                  setSearchParams(
                    (prev) => {
                      const next = new URLSearchParams(prev)
                      if (value === 'all') next.delete('scope')
                      else next.set('scope', value)
                      return next
                    },
                    { replace: true }
                  )
                }}
              >
                <SelectTrigger className="h-8 w-full text-xs">
                  <SelectValue placeholder="全部路由" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">全部路由</SelectItem>
                  <SelectItem value="personal">个人空间</SelectItem>
                  <SelectItem value="shared">协作团队</SelectItem>
                </SelectContent>
              </Select>
            </div>
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
                {filteredRoutes.map((route) => (
                  <RouteSidebarItem
                    key={route.id}
                    route={route}
                    teamLabel={routeTeamLabel(route, teamNameById)}
                    selected={route.id === selectedId}
                    createMode={createMode}
                    onSelect={selectRoute}
                  />
                ))}
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
            allowPersonalBatchAdd={allowCreatePersonalBatchAdd}
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
          <div className="flex min-w-0 flex-col gap-4">
            <RouteTopologyEditor
              route={selectedRoute}
              models={models}
              pickerModels={pickerModels}
              isSaving={updateMutation.isPending}
              isDeleting={deleteMutation.isPending}
              modelsLoading={modelsLoading}
              teamLabel={selectedRouteTeamLabel}
              readOnly={selectedRoute !== null && !selectedRouteEditable}
              allowPersonalBatchAdd={isPersonalRouteContext}
              onSave={(_id, body, weightChanges) => {
                if (!selectedRoute) return
                handleSave(selectedRoute, body, weightChanges)
              }}
              onDelete={() => {
                if (!selectedRoute) return
                handleDelete(selectedRoute)
              }}
            />
            {selectedRoute &&
            selectedRoute.source !== 'system' &&
            isPersonalRouteContext &&
            selectedRouteEditable ? (
              <RouteSharePanel
                routeId={selectedRoute.id}
                virtualModel={selectedRoute.virtual_model}
              />
            ) : null}
          </div>
        )}
      </div>

      {workspaceTeamIsShared ? (
        <SharedRoutesPanel teamId={workspaceTeamId} canManage={canManageWorkspaceTeam} />
      ) : null}
    </div>
  )
}
