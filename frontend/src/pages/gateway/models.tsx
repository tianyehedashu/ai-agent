/**
 * AI Gateway · 模型与路由
 */

import { useEffect, useMemo, useState } from 'react'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Info, Loader2, Pencil, Plus, Route, Zap } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'

import {
  gatewayApi,
  GATEWAY_MODEL_TEST_SUPPORTED_CAPABILITIES,
  type GatewayModel,
  type GatewayModelCreateBody,
  type GatewayModelPreset,
  type GatewayModelRouteUsageItem,
  type GatewayModelUpdateBody,
  type GatewayRoute,
  type GatewayRouteCreateBody,
  type GatewayRouteUpdateBody,
  type ProviderCredential,
} from '@/api/gateway'
import { ModelStatusBadge } from '@/components/model-status-badge'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useToast } from '@/hooks/use-toast'
import { PROVIDER_CHANNEL_FILTER_HINT_GATEWAY } from '@/lib/provider-channel-hint'
import { cn } from '@/lib/utils'
import { MODEL_PROVIDERS } from '@/types/user-model'

const MANUAL_PRESET = '__manual__'
const NO_CREDENTIAL = '__none__'

const CAPABILITIES = [
  'chat',
  'embedding',
  'image',
  'video_generation',
  'moderation',
  'audio_transcription',
  'audio_speech',
  'rerank',
] as const

const MODEL_TYPE_LABELS: Record<string, string> = {
  text: '文本',
  image: '视觉',
  image_gen: '生图',
  video: '视频',
}

/** 与 backend ``GATEWAY_MODEL_TEST_SUPPORTED_CAPABILITIES``（model_test_constants.py）一致。 */
const TESTABLE_CAPABILITIES: ReadonlySet<string> = new Set(
  GATEWAY_MODEL_TEST_SUPPORTED_CAPABILITIES
)

function ModelEndpointAndFeatureCell({ model }: { model: GatewayModel }): React.JSX.Element {
  const types = model.model_types ?? []
  const sc = model.selector_capabilities
  const extraTags: string[] = []
  if (sc?.supports_reasoning === true) extraTags.push('reasoning')
  if (sc?.supports_json_mode === false) extraTags.push('无 JSON 模式')

  return (
    <div className="flex min-w-[7rem] flex-col gap-1.5">
      <div className="flex items-center gap-1">
        <Badge variant="outline">{model.capability}</Badge>
        <Tooltip>
          <TooltipTrigger asChild>
            <button
              type="button"
              className="inline-flex rounded-sm text-muted-foreground hover:text-foreground"
              aria-label="调用面说明"
            >
              <Info className="h-3 w-3" />
            </button>
          </TooltipTrigger>
          <TooltipContent side="bottom" className="max-w-xs text-xs leading-relaxed">
            调用面 = 该别名默认走的 OpenAI 兼容 HTTP 入口（如 chat / image / video_generation）。
            下方芯片为产品特性（文本 / 视觉 / 生图 / 视频等），来自 tags，可与调用面组合出现。
          </TooltipContent>
        </Tooltip>
      </div>
      <div className="flex flex-wrap gap-1">
        {types.map((t) => (
          <Badge key={t} variant="secondary" className="text-[10px] font-normal">
            {MODEL_TYPE_LABELS[t] ?? t}
          </Badge>
        ))}
        {extraTags.map((t) => (
          <Badge key={t} variant="outline" className="text-[10px] font-normal">
            {t}
          </Badge>
        ))}
      </div>
    </div>
  )
}

const ROUTING_STRATEGIES = [
  'simple-shuffle',
  'least-busy',
  'usage-based-routing',
  'latency-based-routing',
  'cost-based-routing',
] as const

const MODEL_TABLE_COLSPAN = 11

/** 与概览页一致：对齐后端 Decimal / JSON 数字 */
function coalesceNumber(value: unknown): number {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string' && value.trim() !== '') {
    const n = Number(value)
    if (Number.isFinite(n)) return n
  }
  return 0
}

interface ModelFormValues {
  presetId: string
  name: string
  capability: string
  realModel: string
  credentialId: string
  provider: string
  weight: string
  rpmLimit: string
  tpmLimit: string
}

interface RouteFormValues {
  virtualModel: string
  primaryModels: string
  fallbacksGeneral: string
  fallbacksContentPolicy: string
  fallbacksContextWindow: string
  strategy: string
}

const emptyModelForm: ModelFormValues = {
  presetId: MANUAL_PRESET,
  name: '',
  capability: 'chat',
  realModel: '',
  credentialId: '',
  provider: 'openai',
  weight: '1',
  rpmLimit: '',
  tpmLimit: '',
}

const emptyRouteForm: RouteFormValues = {
  virtualModel: '',
  primaryModels: '',
  fallbacksGeneral: '',
  fallbacksContentPolicy: '',
  fallbacksContextWindow: '',
  strategy: 'simple-shuffle',
}

export default function GatewayModelsPage(): React.JSX.Element {
  return (
    <Tabs defaultValue="models">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-2xl font-semibold">模型与路由</h2>
        <TabsList>
          <TabsTrigger value="models">模型</TabsTrigger>
          <TabsTrigger value="routes">路由</TabsTrigger>
        </TabsList>
      </div>
      <TabsContent value="models">
        <ModelsTable />
      </TabsContent>
      <TabsContent value="routes">
        <RoutesTable />
      </TabsContent>
    </Tabs>
  )
}

function ModelsTable(): React.JSX.Element {
  const { canWrite } = useGatewayPermission()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [searchParams, setSearchParams] = useSearchParams()
  const credentialFilter = searchParams.get('credentialId') ?? ''
  const highlightModelId = searchParams.get('modelId') ?? ''
  const [open, setOpen] = useState(false)
  const [editingModel, setEditingModel] = useState<GatewayModel | null>(null)
  const [providerFilter, setProviderFilter] = useState<string>('')
  const [usageDays, setUsageDays] = useState<1 | 7 | 30>(7)
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

  const usageByRouteName = useMemo(() => {
    const m = new Map<string, GatewayModelRouteUsageItem>()
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

  function channelLabel(id: string): string {
    return MODEL_PROVIDERS.find((p) => p.id === id)?.name ?? id
  }
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
    const m = new Map<string, ProviderCredential>()
    for (const c of credentials ?? []) {
      m.set(c.id, c)
    }
    return m
  }, [credentials])

  const createMutation = useMutation({
    mutationFn: gatewayApi.createModel,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'models'] })
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'models', 'usage-summary'] })
      setOpen(false)
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
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'models', 'usage-summary'] })
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

  return (
    <div className="space-y-3">
      {credentialFilter ? (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-primary/20 bg-primary/5 px-3 py-2 text-sm">
          <span className="text-muted-foreground">
            当前按凭据筛选：
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
                <span className="ml-1 font-medium text-foreground">{fc.name}</span>
              )
            })()}
          </span>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 shrink-0"
            type="button"
            onClick={() => {
              const next = new URLSearchParams(searchParams)
              next.delete('credentialId')
              next.delete('modelId')
              setSearchParams(next, { replace: true })
            }}
          >
            清除筛选
          </Button>
        </div>
      ) : null}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="space-y-1">
          <p className="text-sm text-muted-foreground">
            请先前往{' '}
            <Link
              to="/gateway/credentials?tab=team"
              className="text-primary underline-offset-4 hover:underline"
            >
              凭据管理
            </Link>{' '}
            配置并启用团队凭据，再注册模型；已注册模型会被 Gateway Router 拉取
          </p>
          <div className="flex max-w-xs flex-col gap-1">
            <Label htmlFor="gw-model-channel" className="text-xs">
              按接入通道筛选
            </Label>
            <Select
              value={providerFilter || '__all__'}
              onValueChange={(v) => {
                setProviderFilter(v === '__all__' ? '' : v)
              }}
            >
              <SelectTrigger id="gw-model-channel" className="h-8 w-full sm:w-[220px]">
                <SelectValue placeholder="全部" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__all__">全部</SelectItem>
                {providerChoices.map((id) => (
                  <SelectItem key={id} value={id}>
                    {channelLabel(id)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">{PROVIDER_CHANNEL_FILTER_HINT_GATEWAY}</p>
          </div>
          <div className="flex max-w-xs flex-col gap-1">
            <Label className="text-xs">用量统计区间</Label>
            <div className="flex flex-wrap gap-1 rounded-md border bg-background p-0.5">
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
                  {d === 1 ? '24 小时' : d === 7 ? '7 天' : '30 天'}
                </Button>
              ))}
            </div>
          </div>
        </div>
        {canWrite && (
          <Button
            size="sm"
            className="shrink-0 self-start sm:self-auto"
            onClick={() => {
              setOpen(true)
            }}
          >
            <Plus className="mr-1.5 h-4 w-4" />
            注册模型
          </Button>
        )}
      </div>

      <TooltipProvider delayDuration={200}>
        <Card>
          <CardContent className="p-0">
            <table className="w-full text-sm">
              <thead className="border-b bg-muted/30 text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="px-4 py-2 text-left font-medium">名称</th>
                  <th className="px-4 py-2 text-left font-medium">调用面 / 特性</th>
                  <th className="px-4 py-2 text-left font-medium">真实模型</th>
                  <th className="px-4 py-2 text-left font-medium">提供商</th>
                  <th className="px-4 py-2 text-left font-medium">凭据</th>
                  <th className="px-4 py-2 text-left font-medium">权重</th>
                  <th className="px-4 py-2 text-left font-medium">每分钟请求 / 每分钟令牌</th>
                  <th className="px-4 py-2 text-left font-medium">
                    <span className="inline-flex items-center gap-1 normal-case">
                      用量
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <button
                            type="button"
                            className="inline-flex rounded-sm text-muted-foreground hover:text-foreground"
                            aria-label="用量说明"
                          >
                            <Info className="h-3.5 w-3.5" />
                          </button>
                        </TooltipTrigger>
                        <TooltipContent side="bottom" className="max-w-xs text-xs leading-relaxed">
                          用量 = 经 Router 命中该注册模型（deployment_gateway_model_id）的调用 +
                          未写 deployment 时按请求 model（route_name）与注册别名匹配的历史/直连。
                          经路由虚拟名进线时，前者仍归到实际命中的 deployment 行。 「当前工作区」=
                          当前 X-Team-Id；「按账号」= 登录用户跨工作区。
                        </TooltipContent>
                      </Tooltip>
                    </span>
                  </th>
                  <th className="px-4 py-2 text-left font-medium">连通性</th>
                  <th className="px-4 py-2 text-left font-medium">启用</th>
                  <th className="px-4 py-2 text-left font-medium">操作</th>
                </tr>
              </thead>
              <tbody>
                {isLoading && (
                  <tr>
                    <td
                      colSpan={MODEL_TABLE_COLSPAN}
                      className="px-4 py-6 text-center text-muted-foreground"
                    >
                      加载中...
                    </td>
                  </tr>
                )}
                {!isLoading && (items?.length ?? 0) === 0 && (
                  <tr>
                    <td
                      colSpan={MODEL_TABLE_COLSPAN}
                      className="px-4 py-6 text-center text-muted-foreground"
                    >
                      暂无注册模型
                    </td>
                  </tr>
                )}
                {items?.map((m: GatewayModel) => {
                  const isTestable = TESTABLE_CAPABILITIES.has(m.capability)
                  const isTesting = testMutation.isPending && testMutation.variables === m.id
                  const cred = credentialsById.get(m.credential_id)
                  const credLabel = cred
                    ? `${cred.name} · ${cred.scope}`
                    : `${m.credential_id.slice(0, 8)}…`
                  const urow = usageByRouteName.get(m.name)
                  const wsReq = urow?.workspace.requests ?? 0
                  const wsTok =
                    (urow?.workspace.input_tokens ?? 0) + (urow?.workspace.output_tokens ?? 0)
                  const usReq = urow?.user.requests ?? 0
                  const usTok = (urow?.user.input_tokens ?? 0) + (urow?.user.output_tokens ?? 0)
                  return (
                    <tr
                      key={m.id}
                      className={cn(
                        'border-b last:border-0 hover:bg-muted/20',
                        highlightModelId === m.id && 'bg-primary/10'
                      )}
                    >
                      <td className="px-4 py-2 font-mono text-xs">{m.name}</td>
                      <td className="px-4 py-2 align-top text-xs">
                        <ModelEndpointAndFeatureCell model={m} />
                      </td>
                      <td className="px-4 py-2 font-mono text-xs">{m.real_model}</td>
                      <td className="px-4 py-2 text-xs">{m.provider}</td>
                      <td className="max-w-[12rem] px-4 py-2 text-xs [overflow-wrap:anywhere]">
                        {cred && canWrite ? (
                          <Link
                            to={`/gateway/credentials/${m.credential_id}`}
                            className="text-primary underline-offset-4 hover:underline"
                            title={m.credential_id}
                          >
                            {credLabel}
                          </Link>
                        ) : (
                          <span
                            className={cred ? 'text-foreground' : 'text-muted-foreground'}
                            title={m.credential_id}
                          >
                            {credLabel}
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-2 text-xs tabular-nums">{m.weight}</td>
                      <td className="px-4 py-2 text-xs tabular-nums">
                        {`${String(m.rpm_limit ?? '∞')} / ${String(m.tpm_limit ?? '∞')}`}
                      </td>
                      <td className="min-w-[9rem] px-4 py-2 align-top text-xs tabular-nums leading-snug text-muted-foreground">
                        {usageLoading ? (
                          <span className="inline-flex items-center gap-1">
                            <Loader2 className="h-3 w-3 animate-spin" />…
                          </span>
                        ) : (
                          <>
                            <div>
                              <span className="text-[10px] uppercase tracking-wide">工作区</span>{' '}
                              {wsReq} 次 / {wsTok} tok
                            </div>
                            <div>
                              <span className="text-[10px] uppercase tracking-wide">账号</span>{' '}
                              {usReq} 次 / {usTok} tok
                            </div>
                            <div className="mt-0.5 text-[10px] text-muted-foreground/80">
                              费用 WS {coalesceNumber(urow?.workspace.cost_usd).toFixed(4)} / U{' '}
                              {coalesceNumber(urow?.user.cost_usd).toFixed(4)} USD
                            </div>
                          </>
                        )}
                      </td>
                      <td className="max-w-[min(24rem,40vw)] px-4 py-2 align-top">
                        <div className="flex min-w-0 flex-col gap-1">
                          <ModelStatusBadge
                            status={m.last_test_status}
                            testedAt={m.last_tested_at}
                            reason={m.last_test_reason}
                          />
                          {m.last_test_status === 'failed' && m.last_test_reason ? (
                            <p
                              className="line-clamp-3 text-xs text-destructive/90 [overflow-wrap:anywhere]"
                              title={m.last_test_reason}
                            >
                              {m.last_test_reason}
                            </p>
                          ) : null}
                        </div>
                      </td>
                      <td className="px-4 py-2">
                        {canWrite ? (
                          <Switch
                            checked={m.enabled}
                            disabled={updateModelMutation.isPending}
                            onCheckedChange={(checked) => {
                              updateModelMutation.mutate({ id: m.id, body: { enabled: checked } })
                            }}
                            aria-label={m.enabled ? '停用模型' : '启用模型'}
                          />
                        ) : (
                          <span className="text-xs text-muted-foreground">
                            {m.enabled ? '启用' : '禁用'}
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-2">
                        <div className="flex items-center gap-1">
                          {canWrite && (
                            <Button
                              size="icon"
                              variant="ghost"
                              className="h-7 w-7"
                              disabled={!isTestable || isTesting}
                              title={isTestable ? '测试连通性' : '该 capability 暂不支持连通性测试'}
                              onClick={() => {
                                testMutation.mutate(m.id)
                              }}
                            >
                              {isTesting ? (
                                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                              ) : (
                                <Zap className="h-3.5 w-3.5" />
                              )}
                            </Button>
                          )}
                          {canWrite && (
                            <Button
                              size="icon"
                              variant="ghost"
                              className="h-7 w-7"
                              title="编辑模型"
                              onClick={() => {
                                setEditingModel(m)
                              }}
                            >
                              <Pencil className="h-3.5 w-3.5" />
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </CardContent>
        </Card>
      </TooltipProvider>

      <CreateModelDialog
        open={open}
        onOpenChange={setOpen}
        presets={presets ?? []}
        credentials={activeCredentials}
        onSubmit={(body) => {
          createMutation.mutate(body)
        }}
      />
      <EditModelDialog
        model={editingModel}
        credentials={credentials ?? []}
        onOpenChange={(o) => {
          if (!o) {
            setEditingModel(null)
          }
        }}
        onSubmit={(id, body) => {
          updateModelMutation.mutate(
            { id, body },
            {
              onSuccess: () => {
                setEditingModel(null)
              },
            }
          )
        }}
        isPending={updateModelMutation.isPending}
      />
    </div>
  )
}

function RoutesTable(): React.JSX.Element {
  const { canWrite } = useGatewayPermission()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [open, setOpen] = useState(false)

  const { data: items, isLoading } = useQuery({
    queryKey: ['gateway', 'routes'],
    queryFn: () => gatewayApi.listRoutes(),
  })
  const { data: models } = useQuery({
    queryKey: ['gateway', 'models'],
    queryFn: () => gatewayApi.listModels(),
  })
  const createMutation = useMutation({
    mutationFn: gatewayApi.createRoute,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'routes'] })
      setOpen(false)
      toast({ title: '路由已创建' })
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '创建失败', description: e.message })
    },
  })
  const updateRouteMutation = useMutation({
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
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          路由用于为虚拟模型配置主模型、Fallback 和全局 Router 策略
        </p>
        {canWrite && (
          <Button
            size="sm"
            onClick={() => {
              setOpen(true)
            }}
          >
            <Route className="mr-1.5 h-4 w-4" />
            新增路由
          </Button>
        )}
      </div>

      <Card>
        <CardContent className="p-0">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/30 text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-4 py-2 text-left font-medium">虚拟模型</th>
                <th className="px-4 py-2 text-left font-medium">策略</th>
                <th className="px-4 py-2 text-left font-medium">主模型</th>
                <th className="px-4 py-2 text-left font-medium">通用 Fallback</th>
                <th className="px-4 py-2 text-left font-medium">启用</th>
              </tr>
            </thead>
            <tbody>
              {isLoading && (
                <tr>
                  <td colSpan={5} className="px-4 py-6 text-center text-muted-foreground">
                    加载中...
                  </td>
                </tr>
              )}
              {!isLoading && (items?.length ?? 0) === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-6 text-center text-muted-foreground">
                    暂无路由
                  </td>
                </tr>
              )}
              {items?.map((r: GatewayRoute) => (
                <tr key={r.id} className="border-b last:border-0 hover:bg-muted/20">
                  <td className="px-4 py-2 font-mono text-xs">{r.virtual_model}</td>
                  <td className="px-4 py-2 font-mono text-xs">{r.strategy}</td>
                  <td className="px-4 py-2 text-xs">{r.primary_models.join(', ')}</td>
                  <td className="px-4 py-2 text-xs">{r.fallbacks_general.join(', ') || '—'}</td>
                  <td className="px-4 py-2">
                    {canWrite ? (
                      <Switch
                        checked={r.enabled}
                        disabled={updateRouteMutation.isPending}
                        onCheckedChange={(checked) => {
                          updateRouteMutation.mutate({ id: r.id, body: { enabled: checked } })
                        }}
                        aria-label={r.enabled ? '停用路由' : '启用路由'}
                      />
                    ) : (
                      <span className="text-xs text-muted-foreground">
                        {r.enabled ? '启用' : '禁用'}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>

      <CreateRouteDialog
        open={open}
        onOpenChange={setOpen}
        models={models ?? []}
        onSubmit={(body) => {
          createMutation.mutate(body)
        }}
      />
    </div>
  )
}

function CreateModelDialog({
  open,
  onOpenChange,
  presets,
  credentials,
  onSubmit,
}: Readonly<{
  open: boolean
  onOpenChange: (v: boolean) => void
  presets: GatewayModelPreset[]
  credentials: ProviderCredential[]
  onSubmit: (body: GatewayModelCreateBody) => void
}>): React.JSX.Element {
  const [values, setValues] = useState<ModelFormValues>(emptyModelForm)

  const selectedPreset = useMemo(
    () => presets.find((p) => p.id === values.presetId),
    [presets, values.presetId]
  )

  const credentialOptions = useMemo(() => {
    const matching = credentials.filter((c) => c.provider === values.provider)
    return matching.length > 0 ? matching : credentials
  }, [credentials, values.provider])

  function handlePresetChange(presetId: string): void {
    if (presetId === MANUAL_PRESET) {
      setValues({ ...values, presetId })
      return
    }
    const preset = presets.find((item) => item.id === presetId)
    if (!preset) return
    const matchingCredential = credentials.find((c) => c.provider === preset.provider)
    setValues({
      ...values,
      presetId,
      name: preset.id,
      capability: preset.capability,
      realModel: preset.real_model,
      provider: preset.provider,
      credentialId: matchingCredential?.id ?? values.credentialId,
    })
  }

  function submit(): void {
    if (!values.name.trim() || !values.realModel.trim() || !values.credentialId) return
    onSubmit({
      name: values.name.trim(),
      capability: values.capability,
      real_model: values.realModel.trim(),
      credential_id: values.credentialId,
      provider: values.provider.trim(),
      weight: parsePositiveInt(values.weight) ?? 1,
      rpm_limit: parsePositiveInt(values.rpmLimit),
      tpm_limit: parsePositiveInt(values.tpmLimit),
      tags: selectedPreset ? buildPresetTags(selectedPreset) : null,
    })
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>注册模型</DialogTitle>
        </DialogHeader>
        <TooltipProvider delayDuration={200}>
          <div className="grid gap-4 py-2 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <Label>常用模型</Label>
              <Select value={values.presetId} onValueChange={handlePresetChange}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={MANUAL_PRESET}>手动配置</SelectItem>
                  {presets.map((preset) => (
                    <SelectItem key={preset.id} value={preset.id}>
                      {preset.name} · {preset.provider}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {selectedPreset && (
              <div className="rounded-md border bg-muted/20 p-3 text-xs text-muted-foreground sm:col-span-2">
                <div className="mb-2 flex flex-wrap gap-1.5">
                  {selectedPreset.recommended_for.map((tag) => (
                    <Badge key={tag} variant="secondary">
                      {tag}
                    </Badge>
                  ))}
                  {selectedPreset.supports_vision && <Badge variant="outline">vision</Badge>}
                  {selectedPreset.supports_reasoning && <Badge variant="outline">reasoning</Badge>}
                  {selectedPreset.supports_tools && <Badge variant="outline">tools</Badge>}
                  {(selectedPreset.model_types ?? []).map((t) => (
                    <Badge key={t} variant="outline" className="text-[10px] font-normal">
                      {MODEL_TYPE_LABELS[t] ?? t}
                    </Badge>
                  ))}
                </div>
                <p>{selectedPreset.description || selectedPreset.id}</p>
              </div>
            )}

            <div>
              <Label>模型别名</Label>
              <Input
                value={values.name}
                onChange={(e) => {
                  setValues({ ...values, name: e.target.value })
                }}
                placeholder="deepseek/deepseek-chat"
              />
            </div>
            <div>
              <div className="mb-1 flex items-center gap-1.5">
                <Label htmlFor="gw-model-capability">主调用面</Label>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <button
                      type="button"
                      id="gw-capability-help"
                      className="inline-flex rounded-sm text-muted-foreground hover:text-foreground"
                      aria-label="主调用面说明"
                    >
                      <Info className="h-3.5 w-3.5" />
                    </button>
                  </TooltipTrigger>
                  <TooltipContent side="right" className="max-w-xs text-xs leading-relaxed">
                    与 OpenAI 兼容路由一致（如 chat、image、video_generation）；多模态能力请在 tags
                    中维护，列表中会单独显示特性芯片。
                  </TooltipContent>
                </Tooltip>
              </div>
              <Select
                value={values.capability}
                onValueChange={(v) => {
                  setValues({ ...values, capability: v })
                }}
              >
                <SelectTrigger id="gw-model-capability">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {CAPABILITIES.map((capability) => (
                    <SelectItem key={capability} value={capability}>
                      {capability}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>真实模型</Label>
              <Input
                value={values.realModel}
                onChange={(e) => {
                  setValues({ ...values, realModel: e.target.value })
                }}
                placeholder="provider/model 或模型 ID"
              />
            </div>
            <div>
              <Label>提供商</Label>
              <Input
                value={values.provider}
                onChange={(e) => {
                  setValues({ ...values, provider: e.target.value })
                }}
                placeholder="openai / deepseek / dashscope"
              />
            </div>
            <div className="sm:col-span-2">
              <Label>凭据</Label>
              <Select
                value={values.credentialId || NO_CREDENTIAL}
                onValueChange={(v) => {
                  setValues({ ...values, credentialId: v === NO_CREDENTIAL ? '' : v })
                }}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={NO_CREDENTIAL}>未选择</SelectItem>
                  {credentialOptions.map((credential) => (
                    <SelectItem key={credential.id} value={credential.id}>
                      {credential.name} · {credential.provider}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {credentials.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  当前没有已启用的团队凭据，请先到{' '}
                  <Link
                    to="/gateway/credentials?tab=team"
                    className="text-primary underline-offset-4 hover:underline"
                    onClick={() => {
                      onOpenChange(false)
                    }}
                  >
                    凭据管理
                  </Link>{' '}
                  添加并启用。
                </p>
              ) : null}
            </div>
            <div>
              <Label>权重</Label>
              <Input
                inputMode="numeric"
                value={values.weight}
                onChange={(e) => {
                  setValues({ ...values, weight: e.target.value })
                }}
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>每分钟请求数</Label>
                <Input
                  inputMode="numeric"
                  value={values.rpmLimit}
                  onChange={(e) => {
                    setValues({ ...values, rpmLimit: e.target.value })
                  }}
                  placeholder="不限"
                />
              </div>
              <div>
                <Label>每分钟令牌数</Label>
                <Input
                  inputMode="numeric"
                  value={values.tpmLimit}
                  onChange={(e) => {
                    setValues({ ...values, tpmLimit: e.target.value })
                  }}
                  placeholder="不限"
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="ghost"
              onClick={() => {
                onOpenChange(false)
              }}
            >
              取消
            </Button>
            <Button
              onClick={submit}
              disabled={
                !values.name.trim() ||
                !values.realModel.trim() ||
                !values.credentialId ||
                credentials.length === 0
              }
            >
              注册
            </Button>
          </DialogFooter>
        </TooltipProvider>
      </DialogContent>
    </Dialog>
  )
}

function EditModelDialog({
  model,
  credentials,
  onOpenChange,
  onSubmit,
  isPending,
}: Readonly<{
  model: GatewayModel | null
  credentials: ProviderCredential[]
  onOpenChange: (open: boolean) => void
  onSubmit: (id: string, body: GatewayModelUpdateBody) => void
  isPending: boolean
}>): React.JSX.Element {
  const open = model !== null
  const [realModel, setRealModel] = useState('')
  const [credentialId, setCredentialId] = useState('')
  const [weight, setWeight] = useState('1')
  const [rpmLimit, setRpmLimit] = useState('')
  const [tpmLimit, setTpmLimit] = useState('')

  const provider = model?.provider ?? ''

  const credentialOptions = useMemo(() => {
    const pool = credentials.filter(
      (c) => c.is_active || (model !== null && c.id === model.credential_id)
    )
    const matching = pool.filter((c) => c.provider === provider)
    return matching.length > 0 ? matching : pool
  }, [credentials, model, provider])

  useEffect(() => {
    if (model) {
      setRealModel(model.real_model)
      setCredentialId(model.credential_id)
      setWeight(String(model.weight))
      setRpmLimit(model.rpm_limit !== null ? String(model.rpm_limit) : '')
      setTpmLimit(model.tpm_limit !== null ? String(model.tpm_limit) : '')
    }
  }, [model])

  function submitEdit(): void {
    if (!model || !realModel.trim() || !credentialId) return
    onSubmit(model.id, {
      real_model: realModel.trim(),
      credential_id: credentialId,
      weight: parsePositiveInt(weight) ?? 1,
      rpm_limit: parsePositiveInt(rpmLimit),
      tpm_limit: parsePositiveInt(tpmLimit),
    })
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        onOpenChange(o)
      }}
    >
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>编辑模型</DialogTitle>
        </DialogHeader>
        {model ? (
          <div className="grid gap-3 py-2">
            <div className="flex flex-col gap-2 text-xs text-muted-foreground">
              <p>
                别名 <span className="font-mono text-foreground">{model.name}</span> ·{' '}
                <Badge variant="outline" className="align-middle text-[10px]">
                  {model.capability}
                </Badge>{' '}
                · {model.provider}
              </p>
              {(model.model_types?.length ?? 0) > 0 ? (
                <div className="flex flex-wrap gap-1">
                  {(model.model_types ?? []).map((t) => (
                    <Badge key={t} variant="secondary" className="text-[10px] font-normal">
                      {MODEL_TYPE_LABELS[t] ?? t}
                    </Badge>
                  ))}
                </div>
              ) : null}
            </div>
            <div>
              <Label>真实模型</Label>
              <Input
                value={realModel}
                onChange={(e) => {
                  setRealModel(e.target.value)
                }}
              />
            </div>
            <div>
              <Label>凭据</Label>
              <Select value={credentialId || NO_CREDENTIAL} onValueChange={setCredentialId}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {credentialOptions.map((c) => (
                    <SelectItem key={c.id} value={c.id}>
                      {c.name} · {c.provider}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {credentialOptions.length === 0 ? (
                <p className="mt-1 text-sm text-muted-foreground">
                  没有可用凭据，请先到{' '}
                  <Link
                    to="/gateway/credentials?tab=team"
                    className="text-primary underline-offset-4 hover:underline"
                    onClick={() => {
                      onOpenChange(false)
                    }}
                  >
                    凭据管理
                  </Link>
                  。
                </p>
              ) : null}
            </div>
            <div>
              <Label>权重</Label>
              <Input
                inputMode="numeric"
                value={weight}
                onChange={(e) => {
                  setWeight(e.target.value)
                }}
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>每分钟请求数</Label>
                <Input
                  inputMode="numeric"
                  value={rpmLimit}
                  onChange={(e) => {
                    setRpmLimit(e.target.value)
                  }}
                  placeholder="不限"
                />
              </div>
              <div>
                <Label>每分钟令牌数</Label>
                <Input
                  inputMode="numeric"
                  value={tpmLimit}
                  onChange={(e) => {
                    setTpmLimit(e.target.value)
                  }}
                  placeholder="不限"
                />
              </div>
            </div>
          </div>
        ) : null}
        <DialogFooter>
          <Button
            variant="ghost"
            onClick={() => {
              onOpenChange(false)
            }}
            disabled={isPending}
          >
            取消
          </Button>
          <Button
            onClick={submitEdit}
            disabled={
              isPending ||
              !model ||
              !realModel.trim() ||
              !credentialId ||
              credentialOptions.length === 0
            }
          >
            {isPending ? '保存中…' : '保存'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function CreateRouteDialog({
  open,
  onOpenChange,
  models,
  onSubmit,
}: Readonly<{
  open: boolean
  onOpenChange: (v: boolean) => void
  models: GatewayModel[]
  onSubmit: (body: GatewayRouteCreateBody) => void
}>): React.JSX.Element {
  const [values, setValues] = useState<RouteFormValues>(emptyRouteForm)
  const modelNames = models.map((m) => m.name)

  function submit(): void {
    const primaryModels = parseModelList(values.primaryModels)
    if (!values.virtualModel.trim() || primaryModels.length === 0) return
    onSubmit({
      virtual_model: values.virtualModel.trim(),
      primary_models: primaryModels,
      fallbacks_general: parseModelList(values.fallbacksGeneral),
      fallbacks_content_policy: parseModelList(values.fallbacksContentPolicy),
      fallbacks_context_window: parseModelList(values.fallbacksContextWindow),
      strategy: values.strategy,
    })
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>新增路由</DialogTitle>
        </DialogHeader>
        <div className="space-y-3 py-2">
          <div>
            <Label>虚拟模型</Label>
            <Input
              value={values.virtualModel}
              onChange={(e) => {
                setValues({ ...values, virtualModel: e.target.value })
              }}
              placeholder="agent-default"
            />
          </div>
          <div>
            <Label>主模型</Label>
            <Input
              value={values.primaryModels}
              onChange={(e) => {
                setValues({ ...values, primaryModels: e.target.value })
              }}
              placeholder={modelNames.slice(0, 2).join(', ') || 'model-a, model-b'}
            />
          </div>
          <div>
            <Label>通用 Fallback</Label>
            <Input
              value={values.fallbacksGeneral}
              onChange={(e) => {
                setValues({ ...values, fallbacksGeneral: e.target.value })
              }}
              placeholder="fallback-a, fallback-b"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>内容策略 Fallback</Label>
              <Input
                value={values.fallbacksContentPolicy}
                onChange={(e) => {
                  setValues({ ...values, fallbacksContentPolicy: e.target.value })
                }}
              />
            </div>
            <div>
              <Label>上下文 Fallback</Label>
              <Input
                value={values.fallbacksContextWindow}
                onChange={(e) => {
                  setValues({ ...values, fallbacksContextWindow: e.target.value })
                }}
              />
            </div>
          </div>
          <div>
            <Label>策略</Label>
            <Select
              value={values.strategy}
              onValueChange={(v) => {
                setValues({ ...values, strategy: v })
              }}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {ROUTING_STRATEGIES.map((strategy) => (
                  <SelectItem key={strategy} value={strategy}>
                    {strategy}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
        <DialogFooter>
          <Button
            variant="ghost"
            onClick={() => {
              onOpenChange(false)
            }}
          >
            取消
          </Button>
          <Button
            onClick={submit}
            disabled={
              !values.virtualModel.trim() || parseModelList(values.primaryModels).length === 0
            }
          >
            创建
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function parsePositiveInt(value: string): number | null {
  const trimmed = value.trim()
  if (!trimmed) return null
  const parsed = Number.parseInt(trimmed, 10)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null
}

function parseModelList(value: string): string[] {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter((item) => item.length > 0)
}

function buildPresetTags(preset: GatewayModelPreset): Record<string, unknown> {
  return {
    display_name: preset.name,
    description: preset.description,
    context_window: preset.context_window,
    input_price: preset.input_price,
    output_price: preset.output_price,
    supports_vision: preset.supports_vision,
    supports_tools: preset.supports_tools,
    supports_reasoning: preset.supports_reasoning,
    recommended_for: preset.recommended_for,
  }
}
