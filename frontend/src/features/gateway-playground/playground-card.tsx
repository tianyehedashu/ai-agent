/**
 * 网关在线试调卡片
 *
 * - 多模式：对话 / 视觉理解 / 图片生成 / 视频生成
 * - Key：从服务端 listKeys 选择，按需 reveal 明文（v3，不自动创建）
 * - 模型：按模式过滤团队 / 个人模型
 */

import { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react'
import type React from 'react'

import { useQueries } from '@tanstack/react-query'

import { gatewayApi } from '@/api/gateway'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
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
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import { GATEWAY_DISPLAY_CURRENCY } from '@/features/gateway-pricing/display-currency'
import { useGatewayModelPrices } from '@/features/gateway-pricing/use-gateway-model-prices'
import { Loader2, PlayCircle, RotateCcw, StopCircle } from '@/lib/lucide-icons'
import { cn } from '@/lib/utils'

import { VisionInput } from './modes/vision-input'
import { PlaygroundKeyField } from './playground-key-field'
import {
  endpointPathForMode,
  filterModelsByMode,
  PLAYGROUND_MODE_LABELS,
  type ModelCandidate,
  type PlaygroundMode,
} from './playground-mode-filter'
import { PlaygroundModelField } from './playground-model-field'
import { PlaygroundOutputPanel } from './playground-output-panel'
import { PlaygroundStatusBadge } from './playground-status-badge'
import { usePlaygroundCall } from './use-playground-call'
import { usePlaygroundImageCall } from './use-playground-image'
import { usePlaygroundVideoCall } from './use-playground-video'
import { useSyncApiKeyFromVkey } from './use-sync-api-key-from-vkey'

import type { PlaygroundApiFlavor } from './types'
import type { UsePlaygroundVirtualKeyReturn } from './use-playground-virtual-key'

const DEFAULT_PROMPTS: Record<PlaygroundMode, string> = {
  chat: '请用三句话介绍 AI Gateway 的作用，并给出一个适合接入的场景。',
  vision: '请用三点总结图片内容，识别主要物体、场景关系和任何可能的风险。',
  image_gen:
    '写实风格的 SaaS 产品发布海报，主体是一台展示 AI Gateway 控制台的笔记本电脑，蓝紫渐变背景，干净科技感，16:9。',
  video_gen:
    '生成一段 6 秒产品演示短视频：镜头从团队仪表盘推进到模型调用日志，风格简洁、科技感、平滑运镜。',
}
const DEFAULT_PROMPT = DEFAULT_PROMPTS.chat
const DEFAULT_PROMPT_VALUES = new Set<string>(Object.values(DEFAULT_PROMPTS))
const IMAGE_GEN_SIZES = ['1024x1024', '1024x1792', '1792x1024'] as const

const MODEL_STATUS_RANK: Record<'success' | 'null' | 'failed', number> = {
  success: 0,
  null: 1,
  failed: 2,
}

interface PlaygroundCardProps {
  baseUrl: string
  onModelChange?: (model: string) => void
  /** 由父级调用 ``usePlaygroundVirtualKey`` 注入，避免重复 list/reveal 请求 */
  virtualKey: UsePlaygroundVirtualKeyReturn
}

export function PlaygroundCard({
  baseUrl,
  onModelChange,
  virtualKey,
}: PlaygroundCardProps): React.JSX.Element {
  const apiKeyId = useId()
  const modelSelectId = useId()
  const modelCustomId = useId()
  const promptId = useId()
  const streamId = useId()
  const visionImageUrlId = useId()
  const videoImageUrlId = useId()
  const imageSizeId = useId()
  const imageCountId = useId()

  const [playgroundMode, setPlaygroundMode] = useState<PlaygroundMode>('chat')
  const [apiKey, setApiKey] = useState('')
  const [model, setModel] = useState('')
  const [customModel, setCustomModel] = useState(false)
  const [prompt, setPrompt] = useState(DEFAULT_PROMPT)
  const [stream, setStream] = useState(true)
  const [apiFlavor, setApiFlavor] = useState<PlaygroundApiFlavor>('openai')
  const [showKey, setShowKey] = useState(false)
  const [visionImageUrl, setVisionImageUrl] = useState('')
  const [videoImageUrl, setVideoImageUrl] = useState('')
  const [imageSize, setImageSize] = useState<string>(IMAGE_GEN_SIZES[0])
  const [imageN, setImageN] = useState(1)
  const userEditedKeyRef = useRef(false)

  const chatCall = usePlaygroundCall()
  const imageCall = usePlaygroundImageCall()
  const videoCall = usePlaygroundVideoCall()

  const {
    keys: virtualKeys,
    isLoadingKeys,
    selectedKey,
    selectedKeyId,
    selectKey,
    plain,
    isRevealing,
    revealError,
  } = virtualKey

  const activeCall =
    playgroundMode === 'image_gen'
      ? imageCall
      : playgroundMode === 'video_gen'
        ? videoCall
        : chatCall

  const { status, content, metadata, error, rawResponse, lastRequest, isRunning, cancel } =
    activeCall

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
  const { byName: priceByName } = useGatewayModelPrices(GATEWAY_DISPLAY_CURRENCY)

  useSyncApiKeyFromVkey({
    plain,
    selectedKeyId,
    userEditedRef: userEditedKeyRef,
    setApiKey,
  })

  const candidateModels = useMemo<ModelCandidate[]>(() => {
    const seen = new Map<string, ModelCandidate>()
    for (const item of teamModelsQuery.data ?? []) {
      if (item.enabled && item.name && !seen.has(item.name)) {
        seen.set(item.name, {
          name: item.name,
          scope: 'team',
          status: item.last_test_status,
          capability: item.capability,
          selector_capabilities: item.selector_capabilities,
          model_types: item.model_types,
        })
      }
    }
    for (const item of myModelsQuery.data ?? []) {
      const key = item.name || item.display_name
      if (item.is_active && key && !seen.has(key)) {
        seen.set(key, {
          name: key,
          scope: 'personal',
          status: item.last_test_status,
          capability: item.capability,
          model_types: item.model_types,
        })
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

  const filteredModels = useMemo(
    () => filterModelsByMode(candidateModels, playgroundMode),
    [candidateModels, playgroundMode]
  )

  const { teamCandidates, personalCandidates } = useMemo(() => {
    const team: ModelCandidate[] = []
    const personal: ModelCandidate[] = []
    for (const m of filteredModels) {
      if (m.scope === 'team') team.push(m)
      else personal.push(m)
    }
    return { teamCandidates: team, personalCandidates: personal }
  }, [filteredModels])

  const selectedCandidate = useMemo(
    () => filteredModels.find((m) => m.name === model),
    [filteredModels, model]
  )

  const endpointPath = endpointPathForMode(
    playgroundMode,
    playgroundMode === 'chat' ? apiFlavor : 'openai'
  )
  const showStreamSwitch = playgroundMode === 'chat' || playgroundMode === 'vision'
  const showApiFlavorTabs = playgroundMode === 'chat'

  useEffect(() => {
    if (model && filteredModels.some((m) => m.name === model)) return
    if (customModel) return
    const first = filteredModels[0]?.name
    if (first) setModel(first)
    else setModel('')
  }, [filteredModels, customModel, model, playgroundMode])

  const onModelChangeRef = useRef(onModelChange)
  useEffect(() => {
    onModelChangeRef.current = onModelChange
  })
  useEffect(() => {
    if (model) onModelChangeRef.current?.(model)
  }, [model])

  const resetAllCalls = (): void => {
    chatCall.reset()
    imageCall.reset()
    videoCall.reset()
  }

  const handleModeChange = (mode: PlaygroundMode): void => {
    setPlaygroundMode(mode)
    if (!prompt.trim() || DEFAULT_PROMPT_VALUES.has(prompt)) {
      setPrompt(DEFAULT_PROMPTS[mode])
    }
    resetAllCalls()
  }

  const trimmedKey = apiKey.trim()
  const trimmedModel = model.trim()
  const trimmedPrompt = prompt.trim()
  const trimmedVisionUrl = visionImageUrl.trim()

  const canSubmit =
    Boolean(trimmedKey && trimmedModel && trimmedPrompt) &&
    (playgroundMode !== 'vision' || Boolean(trimmedVisionUrl))

  const showOutputPanel = status !== 'idle' || Boolean(content || error)

  const keyManualMode =
    virtualKeys.length === 0 ||
    selectedKeyId === null ||
    (revealError !== null && selectedKey !== null)
  const keyFieldUserEdited =
    keyManualMode && apiKey.trim() !== '' && (plain === null || apiKey !== plain)

  const handleApiKeyChange = useCallback((value: string) => {
    userEditedKeyRef.current = true
    setApiKey(value)
  }, [])

  const handleShowKeyToggle = useCallback(() => {
    setShowKey((v) => !v)
  }, [])

  const handleSelectKey = useCallback(
    (id: string | null) => {
      selectKey(id)
      setShowKey(false)
    },
    [selectKey]
  )

  const handleUserEditedReset = useCallback(() => {
    userEditedKeyRef.current = false
  }, [])

  const outputEndpoint = useMemo(() => `${baseUrl}${endpointPath}`, [baseUrl, endpointPath])
  const outputPriceRow = useMemo(() => priceByName.get(trimmedModel), [priceByName, trimmedModel])

  const handleSend = (): void => {
    const params = {
      baseUrl,
      apiKey: trimmedKey,
      model: trimmedModel,
      prompt: trimmedPrompt,
    }
    if (playgroundMode === 'image_gen') {
      void imageCall.send({
        ...params,
        size: imageSize,
        n: imageN,
      })
      return
    }
    if (playgroundMode === 'video_gen') {
      void videoCall.send({
        ...params,
        imageUrl: videoImageUrl.trim() || undefined,
      })
      return
    }
    if (playgroundMode === 'vision') {
      void chatCall.send({
        ...params,
        stream,
        flavor: 'openai',
        imageUrl: trimmedVisionUrl,
      })
      return
    }
    void chatCall.send({
      ...params,
      stream,
      flavor: apiFlavor,
    })
  }

  return (
    <Card className="border-border/60 bg-background shadow-sm">
      <CardHeader className="pb-4">
        <div className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex min-w-0 flex-wrap items-center gap-2">
              <CardTitle className="text-base">在线试调</CardTitle>
              <span className="truncate font-mono text-xs text-muted-foreground" translate="no">
                {baseUrl}
                {endpointPath}
              </span>
            </div>
            <PlaygroundStatusBadge status={status} />
          </div>
          <Tabs
            value={playgroundMode}
            onValueChange={(v) => {
              handleModeChange(v as PlaygroundMode)
            }}
          >
            <TabsList className="h-8 flex-wrap">
              {(Object.keys(PLAYGROUND_MODE_LABELS) as PlaygroundMode[]).map((mode) => (
                <TabsTrigger key={mode} value={mode} className="h-7 px-2.5 text-xs">
                  {PLAYGROUND_MODE_LABELS[mode]}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
        </div>
      </CardHeader>
      <CardContent
        className={cn(
          'grid gap-5',
          showOutputPanel && 'xl:grid-cols-[minmax(0,1fr)_minmax(22rem,0.9fr)]'
        )}
      >
        <div className="min-w-0 space-y-4">
          {showApiFlavorTabs ? (
            <Tabs
              value={apiFlavor}
              onValueChange={(v) => {
                setApiFlavor(v as PlaygroundApiFlavor)
                resetAllCalls()
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
          ) : null}

          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-1 2xl:grid-cols-2">
            <PlaygroundKeyField
              apiKeyId={apiKeyId}
              apiKey={apiKey}
              showKey={showKey}
              onApiKeyChange={handleApiKeyChange}
              onShowKeyToggle={handleShowKeyToggle}
              virtualKeys={virtualKeys}
              selectedKeyId={selectedKeyId}
              selectedKey={selectedKey}
              isLoadingKeys={isLoadingKeys}
              isRevealing={isRevealing}
              revealError={revealError}
              userEdited={keyFieldUserEdited}
              onSelectKey={handleSelectKey}
              onUserEditedReset={handleUserEditedReset}
            />
            <PlaygroundModelField
              modelSelectId={modelSelectId}
              modelCustomId={modelCustomId}
              model={model}
              customModel={customModel}
              onModelChange={setModel}
              onCustomModelChange={(nextCustom, nextModel) => {
                setCustomModel(nextCustom)
                if (nextModel !== undefined) setModel(nextModel)
              }}
              teamCandidates={teamCandidates}
              personalCandidates={personalCandidates}
              filteredModels={filteredModels}
              selectedCandidate={selectedCandidate}
              priceByName={priceByName}
              currency={GATEWAY_DISPLAY_CURRENCY}
              playgroundMode={playgroundMode}
              modelsLoading={teamModelsQuery.isLoading || myModelsQuery.isLoading}
            />
          </div>

          {playgroundMode === 'vision' ? (
            <VisionInput
              imageUrlId={visionImageUrlId}
              imageUrl={visionImageUrl}
              onImageUrlChange={setVisionImageUrl}
              disabled={isRunning}
            />
          ) : null}

          {playgroundMode === 'video_gen' ? (
            <VisionInput
              imageUrlId={videoImageUrlId}
              imageUrl={videoImageUrl}
              onImageUrlChange={setVideoImageUrl}
              disabled={isRunning}
              label="参考图片 URL（可选）"
            />
          ) : null}

          <div className="space-y-1.5">
            <Label htmlFor={promptId}>
              {playgroundMode === 'image_gen'
                ? '提示词'
                : playgroundMode === 'video_gen'
                  ? '视频描述'
                  : '用户消息'}
            </Label>
            <Textarea
              id={promptId}
              value={prompt}
              onChange={(e) => {
                setPrompt(e.target.value)
              }}
              rows={4}
              placeholder={DEFAULT_PROMPTS[playgroundMode]}
            />
          </div>

          {playgroundMode === 'image_gen' ? (
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor={imageSizeId}>尺寸</Label>
                <Select value={imageSize} onValueChange={setImageSize}>
                  <SelectTrigger id={imageSizeId} className="font-mono text-sm">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {IMAGE_GEN_SIZES.map((size) => (
                      <SelectItem key={size} value={size} className="font-mono">
                        {size}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor={imageCountId}>数量 (n)</Label>
                <Input
                  id={imageCountId}
                  type="number"
                  min={1}
                  max={4}
                  value={imageN}
                  onChange={(e) => {
                    const n = Number.parseInt(e.target.value, 10)
                    if (!Number.isNaN(n)) setImageN(Math.min(4, Math.max(1, n)))
                  }}
                  className="font-mono"
                />
              </div>
            </div>
          ) : null}

          <div className="flex flex-wrap items-center gap-3 rounded-lg border bg-muted/20 p-2">
            {showStreamSwitch ? (
              <div className="flex items-center gap-2">
                <Switch
                  id={streamId}
                  checked={stream}
                  onCheckedChange={setStream}
                  disabled={isRunning}
                />
                <Label htmlFor={streamId} className="cursor-pointer text-sm">
                  SSE
                </Label>
              </div>
            ) : null}
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
                  onClick={resetAllCalls}
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
                onClick={handleSend}
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
        </div>

        {showOutputPanel ? (
          <div className="min-w-0 xl:sticky xl:top-4 xl:self-start">
            <PlaygroundOutputPanel
              status={status}
              content={content}
              metadata={metadata}
              error={error}
              rawResponse={rawResponse}
              lastRequest={lastRequest}
              priceRow={outputPriceRow}
              currency={GATEWAY_DISPLAY_CURRENCY}
              flavor={playgroundMode === 'chat' ? apiFlavor : 'openai'}
              stream={showStreamSwitch ? stream : false}
              endpoint={outputEndpoint}
              playgroundMode={playgroundMode}
            />
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}
