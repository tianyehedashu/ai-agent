import { useEffect, useMemo, useState } from 'react'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Route, Loader2, Search } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'

import { gatewayApi, type GatewayRouteUpdateBody } from '@/api/gateway'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useToast } from '@/hooks/use-toast'
import { cn } from '@/lib/utils'

import { CreateRouteDialog } from './create-route-dialog'
import { RouteTopologyEditor } from './route-topology-editor'

export function RouteWorkspace(): React.JSX.Element {
  const { canWrite } = useGatewayPermission()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [searchParams, setSearchParams] = useSearchParams()
  const routeIdFromUrl = searchParams.get('routeId') ?? ''

  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [createOpen, setCreateOpen] = useState(false)

  const { data: routes, isLoading } = useQuery({
    queryKey: ['gateway', 'routes'],
    queryFn: () => gatewayApi.listRoutes(),
  })

  const { data: models } = useQuery({
    queryKey: ['gateway', 'models'],
    queryFn: () => gatewayApi.listModels(),
  })

  useEffect(() => {
    if (!routeIdFromUrl || !routes?.length) return
    if (routes.some((r) => r.id === routeIdFromUrl)) {
      setSelectedId(routeIdFromUrl)
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
    mutationFn: gatewayApi.createRoute,
    onSuccess: (created) => {
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'routes'] })
      setCreateOpen(false)
      setSelectedId(created.id)
      toast({ title: '路由已创建' })
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '创建失败', description: e.message })
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: GatewayRouteUpdateBody }) =>
      gatewayApi.updateRoute(id, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'routes'] })
      toast({ title: '路由已更新' })
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '更新失败', description: e.message })
    },
  })

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="max-w-xl text-sm text-muted-foreground">
          虚拟路由定义客户端请求的 <span className="font-mono">model</span> 名与主模型池、Fallback
          及 Router 策略。需先在{' '}
          <Link
            to="/gateway/models?tab=team"
            className="text-primary underline-offset-4 hover:underline"
          >
            模型管理
          </Link>{' '}
          配置供给。
        </p>
        {canWrite ? (
          <Button
            size="sm"
            onClick={() => {
              setCreateOpen(true)
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
            <div className="relative">
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
          </div>
          <ScrollArea className="min-h-[280px] flex-1">
            {isLoading ? (
              <div className="flex justify-center py-12">
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
              </div>
            ) : filteredRoutes.length === 0 ? (
              <p className="px-3 py-12 text-center text-sm text-muted-foreground">暂无路由</p>
            ) : (
              <ul className="divide-y">
                {filteredRoutes.map((r) => (
                  <li key={r.id}>
                    <button
                      type="button"
                      className={cn(
                        'w-full px-3 py-2.5 text-left hover:bg-muted/40',
                        r.id === selectedId && 'bg-primary/10'
                      )}
                      onClick={() => {
                        setSelectedId(r.id)
                        setSearchParams(
                          (prev) => {
                            const n = new URLSearchParams(prev)
                            n.set('routeId', r.id)
                            return n
                          },
                          { replace: true }
                        )
                      }}
                    >
                      <p className="font-mono text-sm font-medium">{r.virtual_model}</p>
                      <p className="mt-0.5 truncate text-xs text-muted-foreground">
                        {r.strategy} · {r.primary_models.join(', ') || '—'}
                      </p>
                      {!r.enabled ? <p className="mt-1 text-xs text-amber-600">已禁用</p> : null}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </ScrollArea>
        </div>

        <RouteTopologyEditor
          route={selectedRoute}
          models={models ?? []}
          isSaving={updateMutation.isPending}
          onSave={(id, body) => {
            updateMutation.mutate({ id, body })
          }}
        />
      </div>

      <CreateRouteDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        models={models ?? []}
        onSubmit={(body) => {
          createMutation.mutate(body)
        }}
        isSubmitting={createMutation.isPending}
      />
    </div>
  )
}
