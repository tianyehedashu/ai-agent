/**
 * 网关在线试调卡片
 *
 * - 直接 POST /v1/chat/completions（同源、Bearer sk-gw-*）
 * - Key：进入页面自动 ensure 一把「调用指南专用」vkey，缓存到 localStorage（v2 schema，多把）
 *        多把缓存时显示下拉切换；可「换一把」「忘记当前」「忘记全部」；亦可手动覆盖输入
 * - 模型：列出团队 / 个人模型，显示连通性状态（已通过 / 未测试 / 失败）
 * - 响应：文本 / Raw JSON 两种视图
 */

import { useEffect, useId, useMemo, useRef, useState } from 'react'
import type React from 'react'

import { useQueries } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { gatewayApi } from '@/api/gateway'
import type { MyPriceRow } from '@/api/gateway'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import { estimateUsageCostDisplay } from '@/features/gateway-pricing/estimate-usage-cost'
import { PricingBadge } from '@/features/gateway-pricing/pricing-badge'
import { useGatewayModelPrices } from '@/features/gateway-pricing/use-gateway-model-prices'
import { usePricingEstimate } from '@/features/gateway-pricing/use-pricing-estimate'
import {
  AlertCircle,
  CheckCircle2,
  CircleDashed,
  Eye,
  EyeOff,
  Loader2,
  PlayCircle,
  RefreshCw,
  RotateCcw,
  Sparkles,
  StopCircle,
  XCircle,
} from '@/lib/lucide-icons'
import { formatMoney } from '@/lib/money'
import { cn } from '@/lib/utils'
import { useUserPreferenceStore } from '@/stores/user-preference'
import type { DisplayCurrency } from '@/types/money'
import type { ModelTestStatus } from '@/types/user-model'

import { usePlaygroundCall } from './use-playground-call'
import { usePlaygroundVirtualKey, type CachedPlaygroundKey } from './use-playground-virtual-key'

import type {
  PlaygroundApiFlavor,
  PlaygroundError,
  PlaygroundMetadata,
  PlaygroundRawResponse,
  PlaygroundStatus,
} from './types'

const DEFAULT_PROMPT = '用一句话介绍你自己。'
const CUSTOM_MODEL_SENTINEL = '__custom__'

function maskPlainKey(plain: string): string {
  if (plain.length <= 12) return plain
  return `${plain.slice(0, 7)}…${plain.slice(-4)}`
}

const MODEL_STATUS_RANK: Record<'success' | 'null' | 'failed', number> = {
  success: 0,
  null: 1,
  failed: 2,
}

interface ModelCandidate {
  name: string
  scope: 'team' | 'personal'
  status: ModelTestStatus
}

interface PlaygroundCardProps {
  baseUrl: string
  /** 试调当前选中的模型回传给上层，便于示例代码联动 */
  onModelChange?: (model: string) => void
}

export function PlaygroundCard({ baseUrl, onModelChange }: PlaygroundCardProps): React.JSX.Element {
  const apiKeyId = useId()
  const modelSelectId = useId()
  const modelCustomId = useId()
  const promptId = useId()
  const streamId = useId()

  const [apiKey, setApiKey] = useState('')
  const [model, setModel] = useState('')
  const [customModel, setCustomModel] = useState(false)
  const [prompt, setPrompt] = useState(DEFAULT_PROMPT)
  const [stream, setStream] = useState(true)
  const [apiFlavor, setApiFlavor] = useState<PlaygroundApiFlavor>('openai')
  const [showKey, setShowKey] = useState(false)
  const userEditedKeyRef = useRef(false)
  const isAnthropic = apiFlavor === 'anthropic'
  const endpointPath = isAnthropic ? '/messages' : '/chat/completions'

  const { status, content, metadata, error, rawResponse, isRunning, send, cancel, reset } =
    usePlaygroundCall()

  const [teamModelsQuery, myModelsQuery] = useQueries({
    queries: [
      {
        queryKey: ['gateway', 'models', 'playground'],
        queryFn: () => gatewayApi.listModels(),
        staleTime: 60_000,
      },
      {
        queryKey: ['gateway', 'my-models', 'playground'],
        queryFn: () => gatewayApi.listMyModels(),
        staleTime: 60_000,
      },
    ],
  })
  const displayCurrency = useUserPreferenceStore((s) => s.displayCurrency)
  const { byName: priceByName } = useGatewayModelPrices(displayCurrency)

  const {
    items: keyItems,
    selected: selectedKey,
    ensuring: ensuringKey,
    error: keyError,
    selectKey,
    regenerate: regenerateKey,
    forget: forgetKey,
  } = usePlaygroundVirtualKey({ autoEnsure: true })

  useEffect(() => {
    if (userEditedKeyRef.current) return
    if (selectedKey?.plain) {
      setApiKey(selectedKey.plain)
    }
  }, [selectedKey])

  const candidateModels = useMemo<ModelCandidate[]>(() => {
    const seen = new Map<string, ModelCandidate>()
    for (const item of teamModelsQuery.data ?? []) {
      if (item.enabled && item.name && !seen.has(item.name)) {
        seen.set(item.name, { name: item.name, scope: 'team', status: item.last_test_status })
      }
    }
    for (const item of myModelsQuery.data ?? []) {
      const key = item.name || item.display_name
      if (item.is_active && key && !seen.has(key)) {
        seen.set(key, { name: key, scope: 'personal', status: item.last_test_status })
      }
    }
    const all = Array.from(seen.values())
    all.sort((a, b) => {
      const ra = MODEL_STATUS_RANK[a.status ?? 'null']
      const rb = MODEL_STATUS_RANK[b.status ?? 'null']
      if (ra !== rb) return ra - rb
      return a.name.localeCompare(b.name)
    })
    return all
  }, [teamModelsQuery.data, myModelsQuery.data])

  const { teamCandidates, personalCandidates } = useMemo(() => {
    const team: ModelCandidate[] = []
    const personal: ModelCandidate[] = []
    for (const m of candidateModels) {
      if (m.scope === 'team') team.push(m)
      else personal.push(m)
    }
    return { teamCandidates: team, personalCandidates: personal }
  }, [candidateModels])

  const selectedCandidate = useMemo(
    () => candidateModels.find((m) => m.name === model),
    [candidateModels, model]
  )

  useEffect(() => {
    if (model || candidateModels.length === 0 || customModel) return
    const first = candidateModels[0]?.name
    if (first) {
      setModel(first)
    }
  }, [candidateModels, customModel, model])

  const onModelChangeRef = useRef(onModelChange)
  useEffect(() => {
    onModelChangeRef.current = onModelChange
  })

  useEffect(() => {
    if (model) onModelChangeRef.current?.(model)
  }, [model])

  const canSubmit = apiKey.trim().length > 0 && model.trim().length > 0 && prompt.trim().length > 0

  const handleSelectChange = (value: string): void => {
    if (value === CUSTOM_MODEL_SENTINEL) {
      setCustomModel(true)
      setModel('')
      return
    }
    setCustomModel(false)
    setModel(value)
  }

  const handleRegenerateKey = async (): Promise<void> => {
    try {
      const created = await regenerateKey()
      userEditedKeyRef.current = false
      setApiKey(created.plain)
      setShowKey(false)
    } catch {
      // 错误已记录在 keyError 中，UI 会展示
    }
  }

  const handleSelectCachedKey = (id: string): void => {
    selectKey(id)
    const item = keyItems.find((i) => i.id === id)
    if (item) {
      userEditedKeyRef.current = false
      setApiKey(item.plain)
      setShowKey(false)
    }
  }

  const handleForgetCurrent = (): void => {
    if (!selectedKey) return
    forgetKey(selectedKey.id)
    userEditedKeyRef.current = false
    if (keyItems.length <= 1) setApiKey('')
  }

  const handleForgetAll = (): void => {
    forgetKey()
    userEditedKeyRef.current = false
    setApiKey('')
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="space-y-1">
            <CardTitle className="text-base">在线试调</CardTitle>
            <CardDescription>
              直接调用{' '}
              <span className="font-mono" translate="no">
                {baseUrl}
                {endpointPath}
              </span>
              ，可在 OpenAI / Anthropic 两种兼容入口与流式 / 非流式之间切换，快速验证 Key
              与模型是否可用。
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <Tabs
              value={apiFlavor}
              onValueChange={(v) => {
                setApiFlavor(v as PlaygroundApiFlavor)
                reset()
              }}
            >
              <TabsList className="h-8">
                <TabsTrigger value="openai" className="h-7 px-2.5 text-xs">
                  OpenAI
                </TabsTrigger>
                <TabsTrigger value="anthropic" className="h-7 px-2.5 text-xs">
                  Anthropic
                </TabsTrigger>
              </TabsList>
            </Tabs>
            <StatusBadge status={status} />
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-1.5">
            <div className="flex items-center justify-between gap-2">
              <Label htmlFor={apiKeyId}>
                虚拟 Key <span className="text-destructive">*</span>
              </Label>
              <div className="flex items-center gap-1">
                {keyItems.length >= 2 ? (
                  <Select value={selectedKey?.id ?? ''} onValueChange={handleSelectCachedKey}>
                    <SelectTrigger
                      className="h-7 w-auto min-w-[10rem] max-w-[14rem] gap-1 px-2 text-xs"
                      aria-label="切换本地缓存的虚拟 Key"
                    >
                      <SelectValue placeholder="切换 Key" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectGroup>
                        <SelectLabel>本地已缓存（{String(keyItems.length)} 把）</SelectLabel>
                        {keyItems.map((item) => (
                          <SelectItem key={item.id} value={item.id}>
                            <span className="flex w-full items-center gap-2">
                              <span className="font-mono text-muted-foreground" translate="no">
                                {maskPlainKey(item.plain)}
                              </span>
                              <span className="truncate text-foreground/90">{item.name}</span>
                            </span>
                          </SelectItem>
                        ))}
                      </SelectGroup>
                    </SelectContent>
                  </Select>
                ) : null}
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-7 gap-1 px-2 text-xs"
                  onClick={() => {
                    void handleRegenerateKey()
                  }}
                  disabled={ensuringKey}
                  aria-busy={ensuringKey}
                >
                  {ensuringKey ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
                  ) : (
                    <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
                  )}
                  {keyItems.length === 0 ? '自动准备' : '换一把'}
                </Button>
              </div>
            </div>
            <div className="relative">
              <Input
                id={apiKeyId}
                value={apiKey}
                onChange={(e) => {
                  userEditedKeyRef.current = true
                  setApiKey(e.target.value)
                }}
                placeholder={ensuringKey ? '正在自动准备…' : 'sk-gw-...'}
                type={showKey ? 'text' : 'password'}
                autoComplete="off"
                spellCheck={false}
                className="pr-10 font-mono"
                translate="no"
                aria-describedby={`${apiKeyId}-hint`}
              />
              <button
                type="button"
                onClick={() => {
                  setShowKey((v) => !v)
                }}
                className="absolute right-2 top-1/2 inline-flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded text-muted-foreground hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                aria-label={showKey ? '隐藏 Key' : '显示 Key'}
              >
                {showKey ? (
                  <EyeOff className="h-4 w-4" aria-hidden="true" />
                ) : (
                  <Eye className="h-4 w-4" aria-hidden="true" />
                )}
              </button>
            </div>
            <ApiKeyHint
              hintId={`${apiKeyId}-hint`}
              ensuring={ensuringKey}
              selected={selectedKey}
              cachedCount={keyItems.length}
              userEdited={userEditedKeyRef.current && apiKey !== selectedKey?.plain}
              error={keyError}
              onForgetCurrent={handleForgetCurrent}
              onForgetAll={handleForgetAll}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor={customModel ? modelCustomId : modelSelectId}>
              模型 <span className="text-destructive">*</span>
            </Label>
            {customModel ? (
              <div className="flex gap-2">
                <Input
                  id={modelCustomId}
                  value={model}
                  onChange={(e) => {
                    setModel(e.target.value)
                  }}
                  placeholder="输入模型别名或虚拟路由名"
                  autoComplete="off"
                  spellCheck={false}
                  className="font-mono"
                  translate="no"
                />
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setCustomModel(false)
                    setModel(candidateModels[0]?.name ?? '')
                  }}
                  disabled={candidateModels.length === 0}
                >
                  从列表选
                </Button>
              </div>
            ) : (
              <Select value={model} onValueChange={handleSelectChange}>
                <SelectTrigger id={modelSelectId} className="font-mono">
                  <SelectValue
                    placeholder={candidateModels.length === 0 ? '暂无可用模型' : '选择模型'}
                  />
                </SelectTrigger>
                <SelectContent>
                  {teamCandidates.length > 0 ? (
                    <SelectGroup>
                      <SelectLabel>团队模型</SelectLabel>
                      {teamCandidates.map((item) => (
                        <ModelOption
                          key={`team-${item.name}`}
                          item={item}
                          priceRow={priceByName.get(item.name)}
                          currency={displayCurrency}
                        />
                      ))}
                    </SelectGroup>
                  ) : null}
                  {personalCandidates.length > 0 ? (
                    <SelectGroup>
                      <SelectLabel>个人模型</SelectLabel>
                      {personalCandidates.map((item) => (
                        <ModelOption
                          key={`personal-${item.name}`}
                          item={item}
                          priceRow={priceByName.get(item.name)}
                          currency={displayCurrency}
                        />
                      ))}
                    </SelectGroup>
                  ) : null}
                  <SelectItem value={CUSTOM_MODEL_SENTINEL}>
                    <span className="text-muted-foreground">✏️ 手动输入…</span>
                  </SelectItem>
                </SelectContent>
              </Select>
            )}
            <ModelHint
              loading={teamModelsQuery.isLoading || myModelsQuery.isLoading}
              selected={selectedCandidate}
              empty={candidateModels.length === 0}
            />
          </div>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor={promptId}>用户消息</Label>
          <Textarea
            id={promptId}
            value={prompt}
            onChange={(e) => {
              setPrompt(e.target.value)
            }}
            rows={3}
            placeholder="输入要发送给模型的内容…"
          />
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <Switch
              id={streamId}
              checked={stream}
              onCheckedChange={(checked) => {
                setStream(checked)
              }}
              disabled={isRunning}
            />
            <Label htmlFor={streamId} className="cursor-pointer">
              流式响应（SSE）
            </Label>
          </div>
          <div className="flex flex-1 flex-wrap items-center justify-end gap-2">
            {isRunning ? (
              <Button type="button" variant="outline" size="sm" onClick={cancel}>
                <StopCircle className="mr-1.5 h-4 w-4" aria-hidden="true" />
                中止
              </Button>
            ) : (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={reset}
                disabled={status === 'idle' && !content && !error}
              >
                <RotateCcw className="mr-1.5 h-4 w-4" aria-hidden="true" />
                清空
              </Button>
            )}
            <Button
              type="button"
              size="sm"
              disabled={!canSubmit || isRunning}
              aria-busy={isRunning}
              onClick={() => {
                void send({
                  baseUrl,
                  apiKey: apiKey.trim(),
                  model: model.trim(),
                  prompt: prompt.trim(),
                  stream,
                  flavor: apiFlavor,
                })
              }}
            >
              {isRunning ? (
                <Loader2 className="mr-1.5 h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <PlayCircle className="mr-1.5 h-4 w-4" aria-hidden="true" />
              )}
              发送
            </Button>
          </div>
        </div>

        <PlaygroundOutput
          status={status}
          content={content}
          metadata={metadata}
          error={error}
          rawResponse={rawResponse}
          priceRow={priceByName.get(model.trim())}
          currency={displayCurrency}
          flavor={apiFlavor}
          stream={stream}
          endpoint={`${baseUrl}${endpointPath}`}
        />
      </CardContent>
    </Card>
  )
}

function ApiKeyHint({
  hintId,
  ensuring,
  selected,
  cachedCount,
  userEdited,
  error,
  onForgetCurrent,
  onForgetAll,
}: Readonly<{
  hintId: string
  ensuring: boolean
  selected: CachedPlaygroundKey | null
  cachedCount: number
  userEdited: boolean
  error: Error | null
  onForgetCurrent: () => void
  onForgetAll: () => void
}>): React.JSX.Element {
  if (ensuring && !selected) {
    return (
      <p id={hintId} className="inline-flex items-center gap-1 text-xs text-muted-foreground">
        <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" />
        正在为你自动准备一把试调 Key…
      </p>
    )
  }
  if (error && !selected) {
    return (
      <p id={hintId} className="text-xs text-destructive">
        自动准备失败：{error.message}。可点击「换一把」重试，或前往{' '}
        <Link to="/gateway/keys" className="underline-offset-4 hover:underline">
          虚拟 Key
        </Link>{' '}
        手动创建。
      </p>
    )
  }
  if (selected) {
    return (
      <p id={hintId} className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
        <span className="inline-flex items-center gap-1 text-emerald-600">
          <Sparkles className="h-3 w-3" aria-hidden="true" />
          {userEdited ? '已使用你的自定义 Key' : '已使用本地缓存 Key'}
        </span>
        {userEdited ? (
          <span className="text-muted-foreground">本地缓存仍保留，可随时切换回来。</span>
        ) : (
          <span className="text-muted-foreground">
            名称 <span className="text-foreground/80">{selected.name}</span>
            {cachedCount >= 2 ? (
              <>
                ；共缓存 <span className="text-foreground/80">{String(cachedCount)}</span>{' '}
                把，可在右上角切换
              </>
            ) : null}
            ；亦可在
            <Link
              to="/gateway/keys"
              className="ml-1 text-primary underline-offset-4 hover:underline"
            >
              虚拟 Key
            </Link>
            页撤销。
          </span>
        )}
        <button
          type="button"
          onClick={onForgetCurrent}
          className="text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
        >
          忘记当前
        </button>
        {cachedCount >= 2 ? (
          <button
            type="button"
            onClick={onForgetAll}
            className="text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
          >
            忘记全部
          </button>
        ) : null}
      </p>
    )
  }
  return (
    <p id={hintId} className="text-xs text-muted-foreground">
      手动粘贴{' '}
      <span className="font-mono" translate="no">
        sk-gw-*
      </span>
      ，或点击「自动准备」创建一把。
    </p>
  )
}

function ModelOption({
  item,
  priceRow,
  currency,
}: Readonly<{
  item: ModelCandidate
  priceRow?: MyPriceRow
  currency: DisplayCurrency
}>): React.JSX.Element {
  return (
    <SelectItem value={item.name}>
      <span className="flex w-full items-center justify-between gap-3">
        <span className="min-w-0 flex-1 truncate font-mono" translate="no">
          {item.name}
        </span>
        <span className="flex shrink-0 items-center gap-2">
          <PricingBadge row={priceRow} currency={currency} className="hidden sm:inline" />
          <ModelStatusBadge status={item.status} />
        </span>
      </span>
    </SelectItem>
  )
}

function ModelStatusBadge({ status }: Readonly<{ status: ModelTestStatus }>): React.JSX.Element {
  if (status === 'success') {
    return (
      <Badge variant="outline" className="gap-1 border-emerald-500/40 text-emerald-600">
        <CheckCircle2 className="h-3 w-3" aria-hidden="true" />
        已通过
      </Badge>
    )
  }
  if (status === 'failed') {
    return (
      <Badge variant="outline" className="gap-1 border-destructive/40 text-destructive">
        <XCircle className="h-3 w-3" aria-hidden="true" />
        失败
      </Badge>
    )
  }
  return (
    <Badge variant="outline" className="gap-1 text-muted-foreground">
      <CircleDashed className="h-3 w-3" aria-hidden="true" />
      未测试
    </Badge>
  )
}

function ModelHint({
  loading,
  selected,
  empty,
}: Readonly<{
  loading: boolean
  selected: ModelCandidate | undefined
  empty: boolean
}>): React.JSX.Element {
  if (loading) {
    return <p className="text-xs text-muted-foreground">正在读取可用模型…</p>
  }
  if (empty) {
    return (
      <p className="text-xs text-muted-foreground">
        你账号当前没有可用模型。可去{' '}
        <Link to="/gateway/models" className="text-primary underline-offset-4 hover:underline">
          模型
        </Link>{' '}
        注册或选择「手动输入」。
      </p>
    )
  }
  if (selected?.status === 'failed') {
    return (
      <p className="text-xs text-destructive">
        该模型最近一次连通性测试失败，可以试调验证或先回到「模型」页修复凭据。
      </p>
    )
  }
  if (selected?.status === 'success') {
    return <p className="text-xs text-muted-foreground">该模型最近一次连通性测试已通过。</p>
  }
  return (
    <p className="text-xs text-muted-foreground">
      候选包含团队 / 个人模型，亦支持手动输入虚拟路由名。
    </p>
  )
}

function StatusBadge({ status }: Readonly<{ status: PlaygroundStatus }>): React.JSX.Element | null {
  if (status === 'idle') return null
  if (status === 'pending') {
    return (
      <Badge variant="secondary" className="gap-1">
        <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" />
        请求中
      </Badge>
    )
  }
  if (status === 'streaming') {
    return (
      <Badge variant="secondary" className="gap-1">
        <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" />
        流式接收中
      </Badge>
    )
  }
  if (status === 'done') {
    return <Badge variant="default">完成</Badge>
  }
  return <Badge variant="destructive">失败</Badge>
}

function PlaygroundOutput({
  status,
  content,
  metadata,
  error,
  rawResponse,
  priceRow,
  currency,
  flavor,
  stream,
  endpoint,
}: Readonly<{
  status: PlaygroundStatus
  content: string
  metadata: PlaygroundMetadata | null
  error: PlaygroundError | null
  rawResponse: PlaygroundRawResponse
  priceRow?: MyPriceRow
  currency: DisplayCurrency
  flavor: PlaygroundApiFlavor
  stream: boolean
  endpoint: string
}>): React.JSX.Element {
  const responseCostLabel =
    metadata?.responseCostUsd !== undefined
      ? formatMoney(metadata.responseCostUsd, { currency: 'USD', precision: 4 })
      : null
  const needEstimate = responseCostLabel === null && metadata !== null
  const apiEstimate = usePricingEstimate({
    gatewayModelId: priceRow?.gateway_model_id,
    inputTokens: metadata?.promptTokens,
    completionTokens: metadata?.completionTokens,
    enabled: needEstimate,
  })
  const localEstimatedCost =
    needEstimate && !apiEstimate.isApiEstimate && !apiEstimate.isLoading
      ? estimateUsageCostDisplay(
          priceRow,
          metadata.promptTokens,
          metadata.completionTokens,
          currency
        )
      : null
  const estimatedCost = apiEstimate.isLoading
    ? '预估计算中…'
    : (apiEstimate.label ?? localEstimatedCost)
  if (status === 'idle' && !content && !error) {
    return (
      <div
        className="rounded-md border border-dashed bg-muted/30 p-4 text-center text-xs text-muted-foreground"
        aria-live="polite"
      >
        发送后将在此展示模型响应（含文本 / Raw JSON 与 metadata）。
      </div>
    )
  }
  const showStreamCursor = status === 'streaming'
  return (
    <div
      className={cn(
        'space-y-2 rounded-md border p-3 transition-colors',
        stream
          ? 'border-amber-500/30 bg-amber-50/30 dark:bg-amber-950/10'
          : 'border-border bg-muted/30'
      )}
      aria-live="polite"
    >
      <ResponseModeHeader
        flavor={flavor}
        stream={stream}
        endpoint={endpoint}
        streaming={status === 'streaming'}
      />
      {error ? <ErrorBlock error={error} /> : null}
      {content || rawResponse ? (
        <Tabs defaultValue="text" className="w-full">
          <TabsList className="h-8">
            <TabsTrigger value="text" className="h-6 px-3 text-xs">
              文本
            </TabsTrigger>
            <TabsTrigger value="json" className="h-6 px-3 text-xs">
              Raw {stream ? 'SSE 摘要' : 'JSON'}
            </TabsTrigger>
          </TabsList>
          <TabsContent value="text">
            <pre
              className={cn(
                'max-h-72 overflow-auto whitespace-pre-wrap break-words rounded-md border bg-background p-4 text-sm leading-relaxed',
                !content && 'text-muted-foreground'
              )}
            >
              <code>
                {content || '（无文本，仅工具调用或空响应）'}
                {showStreamCursor ? (
                  <span
                    className="ml-0.5 inline-block h-3.5 w-1.5 translate-y-0.5 animate-pulse rounded-sm bg-amber-500 align-middle"
                    aria-hidden="true"
                  />
                ) : null}
              </code>
            </pre>
          </TabsContent>
          <TabsContent value="json">
            <pre className="max-h-72 overflow-auto rounded-md border bg-background p-4 text-xs leading-relaxed">
              <code translate="no">{safeStringify(rawResponse)}</code>
            </pre>
          </TabsContent>
        </Tabs>
      ) : null}
      {metadata ? (
        <MetadataRow
          metadata={metadata}
          responseCostLabel={responseCostLabel}
          estimatedCost={estimatedCost}
        />
      ) : null}
    </div>
  )
}

function ResponseModeHeader({
  flavor,
  stream,
  endpoint,
  streaming,
}: Readonly<{
  flavor: PlaygroundApiFlavor
  stream: boolean
  endpoint: string
  streaming: boolean
}>): React.JSX.Element {
  return (
    <div className="flex flex-wrap items-center gap-1.5 text-xs">
      <Badge variant="secondary" className="font-mono">
        {flavor === 'anthropic' ? 'Anthropic · Messages' : 'OpenAI · Chat'}
      </Badge>
      {stream ? (
        <Badge variant="outline" className="gap-1 border-amber-500/40 text-amber-600">
          {streaming ? (
            <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" />
          ) : (
            <Sparkles className="h-3 w-3" aria-hidden="true" />
          )}
          流式 SSE {streaming ? '接收中' : ''}
        </Badge>
      ) : (
        <Badge variant="outline" className="gap-1">
          <CheckCircle2 className="h-3 w-3" aria-hidden="true" />
          非流式 JSON
        </Badge>
      )}
      <span className="ml-1 truncate font-mono text-muted-foreground" translate="no">
        {endpoint}
      </span>
    </div>
  )
}

function ErrorBlock({ error }: Readonly<{ error: PlaygroundError }>): React.JSX.Element {
  return (
    <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
      <div className="mb-1 flex items-center gap-2 font-medium">
        <AlertCircle className="h-4 w-4" aria-hidden="true" />
        调用失败
        {error.httpStatus ? (
          <Badge variant="outline" className="border-destructive/40 font-mono text-destructive">
            {error.httpStatus}
          </Badge>
        ) : null}
        {error.code ? (
          <Badge variant="outline" className="font-mono">
            {error.code}
          </Badge>
        ) : null}
      </div>
      <p className="whitespace-pre-wrap break-words">{error.message}</p>
      <p className="mt-2 text-xs">
        可前往{' '}
        <Link to="/gateway/logs" className="underline-offset-4 hover:underline">
          调用日志
        </Link>{' '}
        查看完整请求与上游错误详情。
      </p>
    </div>
  )
}

function MetadataRow({
  metadata,
  responseCostLabel,
  estimatedCost,
}: Readonly<{
  metadata: PlaygroundMetadata
  responseCostLabel?: string | null
  estimatedCost?: string | null
}>): React.JSX.Element {
  const items: { label: string; value: string }[] = []
  if (metadata.httpStatus !== undefined) {
    items.push({ label: 'HTTP', value: String(metadata.httpStatus) })
  }
  if (metadata.elapsedMs !== undefined) {
    items.push({ label: '耗时', value: `${String(metadata.elapsedMs)} ms` })
  }
  if (metadata.totalTokens !== undefined) {
    items.push({ label: 'Tokens', value: String(metadata.totalTokens) })
  } else if (metadata.completionTokens !== undefined || metadata.promptTokens !== undefined) {
    const promptPart = metadata.promptTokens !== undefined ? String(metadata.promptTokens) : '?'
    const completionPart =
      metadata.completionTokens !== undefined ? String(metadata.completionTokens) : '?'
    items.push({ label: 'Tokens', value: `${promptPart} → ${completionPart}` })
  }
  if (metadata.finishReason) items.push({ label: 'finish', value: metadata.finishReason })
  if (metadata.requestId) items.push({ label: 'id', value: metadata.requestId })
  if (responseCostLabel) {
    items.push({ label: '费用 (USD)', value: responseCostLabel })
  } else if (estimatedCost) {
    items.push({ label: '预估费用', value: estimatedCost })
  }
  if (items.length === 0) return <></>
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
      {items.map((item) => (
        <span key={item.label} className="inline-flex items-center gap-1">
          <span className="uppercase tracking-wide">{item.label}</span>
          <span className="font-mono tabular-nums text-foreground/80" translate="no">
            {item.value}
          </span>
        </span>
      ))}
    </div>
  )
}

function safeStringify(value: unknown): string {
  if (value === null || value === undefined) return '（无）'
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    if (typeof value === 'string') return value
    if (typeof value === 'number' || typeof value === 'boolean' || typeof value === 'bigint') {
      return String(value)
    }
    return '[unserializable]'
  }
}
