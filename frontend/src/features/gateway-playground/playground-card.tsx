/**
 * 网关在线试调卡片
 *
 * - 多模式：对话 / 视觉理解 / 图片生成 / 视频生成
 * - Key：从服务端 listKeys 选择，按需 reveal 明文（v3，不自动创建）
 * - 模型：按模式过滤团队 / 个人模型
 */

import { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react'
import type React from 'react'

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
import {
  temperatureDefaultFromCapabilities,
  temperaturePolicyFromCapabilities,
} from '@/features/gateway-shared/model-selector-capabilities'
import {
  builtinReasoningPlaygroundHint,
  resolveThinkingParamForModel,
  thinkingHintForModel,
  type ThinkingParam,
} from '@/features/gateway-shared/thinking-param'
import { Loader2, PlayCircle, RotateCcw, StopCircle } from '@/lib/lucide-icons'
import { cn } from '@/lib/utils'

import { VisionInput } from './modes/vision-input'
import { PlaygroundCredentialField } from './playground-credential-field'
import { PlaygroundKeyField } from './playground-key-field'
import {
  endpointPathForMode,
  filterModelsByMode,
  filterPlaygroundRouteCandidates,
  buildModelCandidateIndex,
  PLAYGROUND_MODE_LABELS,
  type ModelCandidate,
  type PlaygroundMode,
} from './playground-mode-filter'
import { PlaygroundModelField, type RouteCandidate } from './playground-model-field'
import { PlaygroundOutputPanel } from './playground-output-panel'
import { PlaygroundStatusBadge } from './playground-status-badge'
import { usePlaygroundCall } from './use-playground-call'
import { usePlaygroundImageCall } from './use-playground-image'
import { usePlaygroundVideoCall } from './use-playground-video'
import { useSyncApiKeyFromVkey } from './use-sync-api-key-from-vkey'

import type { PlaygroundApiFlavor } from './types'
import type { PlaygroundModelsSnapshot } from './use-playground-filtered-models'
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

interface PlaygroundCardProps {
  baseUrl: string
  onModelChange?: (model: string) => void
  /** 可选凭据筛选（Guide 页与 URL 同步） */
  credentialId?: string
  onCredentialChange?: (id: string) => void
  /** 由父级调用 ``usePlaygroundVirtualKey`` 注入，避免重复 list/reveal 请求 */
  virtualKey: UsePlaygroundVirtualKeyReturn
  /** 由父级 ``usePlaygroundFilteredModels`` 注入（凭据目录 + 模型候选 + 路由）；卡片内不自行查询 */
  filteredModels: PlaygroundModelsSnapshot
}

export function PlaygroundCard({
  baseUrl,
  onModelChange,
  credentialId: credentialIdProp = '',
  onCredentialChange,
  virtualKey,
  filteredModels: {
    credentialGroups,
    credentialById,
    candidateModels,
    routes,
    modelsLoading,
    credentialsLoading,
    credentialsEmpty,
    teamModelsLoaded,
    myModelsLoaded,
  },
}: PlaygroundCardProps): React.JSX.Element {
  const isCredentialControlled = onCredentialChange !== undefined
  const [localCredentialId, setLocalCredentialId] = useState('')
  const credentialId = isCredentialControlled ? credentialIdProp : localCredentialId
  const handleCredentialChange = useCallback(
    (id: string) => {
      if (onCredentialChange) onCredentialChange(id)
      else setLocalCredentialId(id)
    },
    [onCredentialChange]
  )

  const apiKeyId = useId()
  const credentialSelectId = useId()
  const modelSelectId = useId()
  const modelCustomId = useId()
  const promptId = useId()
  const streamId = useId()
  const thinkingId = useId()
  const temperatureId = useId()
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
  const [thinkingEnabled, setThinkingEnabled] = useState(false)
  const [temperature, setTemperature] = useState(0.7)
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

  const { byName: priceByName } = useGatewayModelPrices(GATEWAY_DISPLAY_CURRENCY)

  useSyncApiKeyFromVkey({
    plain,
    selectedKeyId,
    userEditedRef: userEditedKeyRef,
    setApiKey,
  })

  const modeFilteredModels = useMemo(
    () => filterModelsByMode(candidateModels, playgroundMode),
    [candidateModels, playgroundMode]
  )

  const modelsByName = useMemo(() => buildModelCandidateIndex(candidateModels), [candidateModels])

  const routeCandidates = useMemo<RouteCandidate[]>(
    () =>
      filterPlaygroundRouteCandidates(
        routes,
        credentialId,
        candidateModels,
        playgroundMode,
        modelsByName
      ),
    [routes, credentialId, candidateModels, playgroundMode, modelsByName]
  )

  const { teamCandidates, personalCandidates } = useMemo(() => {
    const team: ModelCandidate[] = []
    const personal: ModelCandidate[] = []
    for (const m of modeFilteredModels) {
      if (m.scope === 'team') team.push(m)
      else personal.push(m)
    }
    return { teamCandidates: team, personalCandidates: personal }
  }, [modeFilteredModels])

  const selectedCandidate = useMemo(
    () => modeFilteredModels.find((m) => m.name === model),
    [modeFilteredModels, model]
  )

  const selectedRoute = useMemo(
    () => routeCandidates.find((r) => r.name === model),
    [routeCandidates, model]
  )

  const endpointPath = endpointPathForMode(
    playgroundMode,
    playgroundMode === 'chat' ? apiFlavor : 'openai'
  )
  const showStreamSwitch = playgroundMode === 'chat' || playgroundMode === 'vision'
  const showApiFlavorTabs = playgroundMode === 'chat'

  useEffect(() => {
    const modelListed =
      modeFilteredModels.some((m) => m.name === model) ||
      routeCandidates.some((r) => r.name === model)
    if (model && modelListed) return
    if (customModel) return
    const first = routeCandidates[0]?.name ?? modeFilteredModels[0]?.name
    if (first) setModel(first)
    else setModel('')
  }, [modeFilteredModels, routeCandidates, customModel, model, playgroundMode])

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

  const modelsListLoaded = teamModelsLoaded && myModelsLoaded

  const thinkingParam = useMemo<ThinkingParam>(
    () =>
      resolveThinkingParamForModel(trimmedModel, selectedCandidate?.selector_capabilities, {
        allowNameFallback: !modelsListLoaded,
      }),
    [trimmedModel, selectedCandidate?.selector_capabilities, modelsListLoaded]
  )

  const temperaturePolicy = useMemo(
    () => temperaturePolicyFromCapabilities(selectedCandidate?.selector_capabilities),
    [selectedCandidate?.selector_capabilities]
  )

  const temperatureInteractive = playgroundMode === 'chat' && temperaturePolicy === 'client'

  const temperatureFixedHint =
    playgroundMode === 'chat' && temperaturePolicy === 'fixed_1'
      ? '推理/思考类模型：temperature 固定为 1.0，无需调整。'
      : null

  const thinkingFlavorMatch =
    (thinkingParam === 'dashscope_enable_thinking' && apiFlavor === 'openai') ||
    (thinkingParam === 'anthropic_extended' && apiFlavor === 'anthropic')

  const thinkingSwitchInteractive = playgroundMode === 'chat' && thinkingFlavorMatch

  const showThinkingSection = playgroundMode === 'chat' && thinkingParam !== 'builtin_reasoning'

  const thinkingModelHint = useMemo(
    () =>
      playgroundMode === 'chat' && !thinkingSwitchInteractive
        ? thinkingHintForModel(trimmedModel, apiFlavor, selectedCandidate?.selector_capabilities, {
            allowNameFallback: !modelsListLoaded,
          })
        : null,
    [
      playgroundMode,
      thinkingSwitchInteractive,
      trimmedModel,
      apiFlavor,
      selectedCandidate?.selector_capabilities,
      modelsListLoaded,
    ]
  )

  const builtinThinkingHint = useMemo(
    () => (playgroundMode === 'chat' ? builtinReasoningPlaygroundHint(thinkingParam) : null),
    [playgroundMode, thinkingParam]
  )

  const handleThinkingCheckedChange = useCallback(
    (checked: boolean) => {
      setThinkingEnabled(checked)
      if (checked && thinkingParam === 'dashscope_enable_thinking') {
        setStream(true)
      }
    },
    [thinkingParam]
  )

  useEffect(() => {
    setThinkingEnabled(false)
  }, [model, apiFlavor, playgroundMode])

  useEffect(() => {
    if (selectedCandidate?.selector_capabilities) {
      setTemperature(temperatureDefaultFromCapabilities(selectedCandidate.selector_capabilities))
    }
  }, [model, selectedCandidate?.selector_capabilities])

  const selectedModelRequestable = useMemo(() => {
    if (customModel) return trimmedModel.length > 0
    if (selectedRoute) {
      return selectedRoute.primaryModels.every((name) => modelsByName.has(name))
    }
    if (selectedCandidate) return true
    return false
  }, [customModel, trimmedModel, selectedRoute, selectedCandidate, modelsByName])

  const canSubmit =
    Boolean(trimmedKey && trimmedModel && trimmedPrompt) &&
    selectedModelRequestable &&
    (playgroundMode !== 'vision' || Boolean(trimmedVisionUrl))

  const thinkingContent = 'thinkingContent' in activeCall ? activeCall.thinkingContent : ''

  const showOutputPanel = status !== 'idle' || Boolean(content || thinkingContent || error)

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
      stream: thinkingEnabled && thinkingParam === 'dashscope_enable_thinking' ? true : stream,
      flavor: apiFlavor,
      enableThinking: thinkingSwitchInteractive ? thinkingEnabled : false,
      temperature: temperatureInteractive ? temperature : undefined,
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
            <PlaygroundCredentialField
              credentialSelectId={credentialSelectId}
              credentialId={credentialId}
              onCredentialChange={handleCredentialChange}
              grouped={credentialGroups}
              selectedSummary={credentialId ? credentialById.get(credentialId) : undefined}
              isLoading={credentialsLoading}
              isEmpty={credentialsEmpty}
            />
            <div className="md:col-span-2 xl:col-span-1 2xl:col-span-2">
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
                routeCandidates={routeCandidates}
                teamCandidates={teamCandidates}
                personalCandidates={personalCandidates}
                filteredModels={modeFilteredModels}
                selectedCandidate={selectedCandidate}
                selectedRoute={selectedRoute}
                priceByName={priceByName}
                currency={GATEWAY_DISPLAY_CURRENCY}
                playgroundMode={playgroundMode}
                modelsLoading={modelsLoading}
              />
            </div>
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

          {builtinThinkingHint ? (
            <p className="rounded-md border border-purple-500/20 bg-purple-500/5 px-3 py-2 text-xs text-muted-foreground">
              {builtinThinkingHint}
            </p>
          ) : null}

          {temperatureFixedHint ? (
            <p className="rounded-md border border-amber-500/20 bg-amber-500/5 px-3 py-2 text-xs text-muted-foreground">
              {temperatureFixedHint}
            </p>
          ) : null}

          {temperatureInteractive ? (
            <div className="space-y-1.5">
              <Label htmlFor={temperatureId}>Temperature ({temperature.toFixed(2)})</Label>
              <input
                id={temperatureId}
                type="range"
                min={0}
                max={2}
                step={0.05}
                value={temperature}
                disabled={isRunning}
                onChange={(e) => {
                  setTemperature(Number.parseFloat(e.target.value))
                }}
                className="w-full accent-primary"
              />
            </div>
          ) : null}

          <div className="flex flex-wrap items-center gap-3 rounded-lg border bg-muted/20 p-2">
            {showStreamSwitch ? (
              <div className="flex items-center gap-2">
                <Switch
                  id={streamId}
                  checked={stream}
                  onCheckedChange={setStream}
                  disabled={
                    isRunning || (thinkingEnabled && thinkingParam === 'dashscope_enable_thinking')
                  }
                />
                <Label htmlFor={streamId} className="cursor-pointer text-sm">
                  SSE
                </Label>
              </div>
            ) : null}
            {showThinkingSection ? (
              <div className="flex min-w-[12rem] flex-1 flex-col gap-1.5 sm:max-w-md">
                <div className="flex items-center gap-2">
                  <Switch
                    id={thinkingId}
                    checked={thinkingSwitchInteractive ? thinkingEnabled : false}
                    onCheckedChange={handleThinkingCheckedChange}
                    disabled={isRunning || !thinkingSwitchInteractive}
                  />
                  <Label
                    htmlFor={thinkingId}
                    className={cn(
                      'text-sm',
                      thinkingSwitchInteractive
                        ? 'cursor-pointer'
                        : 'cursor-not-allowed text-muted-foreground'
                    )}
                  >
                    思考模式
                  </Label>
                </div>
                {!thinkingSwitchInteractive && thinkingModelHint ? (
                  <p className="text-xs leading-relaxed text-muted-foreground">
                    {thinkingModelHint}
                  </p>
                ) : null}
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
              thinkingContent={thinkingContent}
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
