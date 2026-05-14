/**
 * AI Gateway · 模型与路由
 */

import { useEffect, useMemo, useState } from 'react'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2, Plus, Route, Trash2, Zap } from 'lucide-react'

import {
  gatewayApi,
  type GatewayModel,
  type GatewayModelCreateBody,
  type GatewayModelPreset,
  type GatewayRoute,
  type GatewayRouteCreateBody,
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useToast } from '@/hooks/use-toast'
import { PROVIDER_CHANNEL_FILTER_HINT_GATEWAY } from '@/lib/provider-channel-hint'
import { MODEL_PROVIDERS } from '@/types/user-model'

const MANUAL_PRESET = '__manual__'
const NO_CREDENTIAL = '__none__'

const CAPABILITIES = [
  'chat',
  'embedding',
  'image',
  'audio_transcription',
  'audio_speech',
  'rerank',
] as const

/** 与后端 ``_TEST_SUPPORTED_CAPABILITIES`` 保持一致；其它 capability 第一版禁用按钮。 */
const TESTABLE_CAPABILITIES: ReadonlySet<string> = new Set(['chat', 'embedding'])

const ROUTING_STRATEGIES = [
  'simple-shuffle',
  'least-busy',
  'usage-based-routing',
  'latency-based-routing',
  'cost-based-routing',
] as const

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
  const [open, setOpen] = useState(false)
  const [providerFilter, setProviderFilter] = useState<string>('')
  const [providerChoices, setProviderChoices] = useState<string[]>(() =>
    MODEL_PROVIDERS.map((p) => p.id)
  )

  const { data: items, isLoading } = useQuery({
    queryKey: ['gateway', 'models', providerFilter],
    queryFn: () =>
      providerFilter
        ? gatewayApi.listModels({ provider: providerFilter })
        : gatewayApi.listModels(),
  })

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

  const createMutation = useMutation({
    mutationFn: gatewayApi.createModel,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'models'] })
      setOpen(false)
      toast({ title: '模型已注册' })
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '注册失败', description: e.message })
    },
  })
  const deleteMutation = useMutation({
    mutationFn: (id: string) => gatewayApi.deleteModel(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'models'] })
      toast({ title: '已删除' })
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

  return (
    <div className="space-y-3">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="space-y-1">
          <p className="text-sm text-muted-foreground">
            已注册模型会被 Gateway Router 拉取；聊天默认模型名匹配后会进入统一用量日志
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

      <Card>
        <CardContent className="p-0">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/30 text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-4 py-2 text-left font-medium">名称</th>
                <th className="px-4 py-2 text-left font-medium">能力</th>
                <th className="px-4 py-2 text-left font-medium">真实模型</th>
                <th className="px-4 py-2 text-left font-medium">提供商</th>
                <th className="px-4 py-2 text-left font-medium">权重</th>
                <th className="px-4 py-2 text-left font-medium">每分钟请求 / 每分钟令牌</th>
                <th className="px-4 py-2 text-left font-medium">状态</th>
                <th className="px-4 py-2 text-left font-medium">连通性</th>
                <th className="px-4 py-2 text-left font-medium" />
              </tr>
            </thead>
            <tbody>
              {isLoading && (
                <tr>
                  <td colSpan={9} className="px-4 py-6 text-center text-muted-foreground">
                    加载中...
                  </td>
                </tr>
              )}
              {!isLoading && (items?.length ?? 0) === 0 && (
                <tr>
                  <td colSpan={9} className="px-4 py-6 text-center text-muted-foreground">
                    暂无注册模型
                  </td>
                </tr>
              )}
              {items?.map((m: GatewayModel) => {
                const isTestable = TESTABLE_CAPABILITIES.has(m.capability)
                const isTesting = testMutation.isPending && testMutation.variables === m.id
                return (
                  <tr key={m.id} className="border-b last:border-0 hover:bg-muted/20">
                    <td className="px-4 py-2 font-mono text-xs">{m.name}</td>
                    <td className="px-4 py-2 text-xs">
                      <Badge variant="outline">{m.capability}</Badge>
                    </td>
                    <td className="px-4 py-2 font-mono text-xs">{m.real_model}</td>
                    <td className="px-4 py-2 text-xs">{m.provider}</td>
                    <td className="px-4 py-2 text-xs tabular-nums">{m.weight}</td>
                    <td className="px-4 py-2 text-xs tabular-nums">
                      {`${String(m.rpm_limit ?? '∞')} / ${String(m.tpm_limit ?? '∞')}`}
                    </td>
                    <td className="px-4 py-2 text-xs">{m.enabled ? '启用' : '禁用'}</td>
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
                            onClick={() => {
                              if (confirm(`删除 ${m.name}?`)) deleteMutation.mutate(m.id)
                            }}
                          >
                            <Trash2 className="h-3.5 w-3.5 text-destructive" />
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

      <CreateModelDialog
        open={open}
        onOpenChange={setOpen}
        presets={presets ?? []}
        credentials={credentials ?? []}
        onSubmit={(body) => {
          createMutation.mutate(body)
        }}
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
  const deleteMutation = useMutation({
    mutationFn: (id: string) => gatewayApi.deleteRoute(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'routes'] })
      toast({ title: '已删除' })
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
                <th className="px-4 py-2 text-left font-medium">状态</th>
                <th className="px-4 py-2 text-left font-medium" />
              </tr>
            </thead>
            <tbody>
              {isLoading && (
                <tr>
                  <td colSpan={6} className="px-4 py-6 text-center text-muted-foreground">
                    加载中...
                  </td>
                </tr>
              )}
              {!isLoading && (items?.length ?? 0) === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-6 text-center text-muted-foreground">
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
                  <td className="px-4 py-2 text-xs">{r.enabled ? '启用' : '禁用'}</td>
                  <td className="px-4 py-2">
                    {canWrite && (
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-7 w-7"
                        onClick={() => {
                          if (confirm(`删除路由 ${r.virtual_model}?`)) deleteMutation.mutate(r.id)
                        }}
                      >
                        <Trash2 className="h-3.5 w-3.5 text-destructive" />
                      </Button>
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
            <Label>能力</Label>
            <Select
              value={values.capability}
              onValueChange={(v) => {
                setValues({ ...values, capability: v })
              }}
            >
              <SelectTrigger>
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
            disabled={!values.name.trim() || !values.realModel.trim() || !values.credentialId}
          >
            注册
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
