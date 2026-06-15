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
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import { useVkeyGrants } from '@/features/gateway-keys/grants/use-vkey-grants'
import { GATEWAY_DISPLAY_CURRENCY } from '@/features/gateway-pricing/display-currency'
import { useGatewayModelPrices } from '@/features/gateway-pricing/use-gateway-model-prices'
import {
  defaultImageGenSizeForProvider,
  imageGenSizesForProvider,
} from '@/features/gateway-shared/image-gen-size-presets'
import {
  temperatureDefaultFromCapabilities,
  temperaturePolicyFromCapabilities,
} from '@/features/gateway-shared/model-selector-capabilities'
import { resolvePlaygroundImageGenProvider } from '@/features/gateway-shared/resolve-playground-image-gen-provider'
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
import { withReferenceImagePayloadHint } from './playground-error'
import {
  PLAYGROUND_EXAMPLE_PROMPTS,
  PLAYGROUND_EXAMPLE_PROMPT_VALUES,
} from './playground-example-content'
import { PlaygroundImageGenSizeField } from './playground-image-gen-size-field'
import { PlaygroundKeyField } from './playground-key-field'
import {
  endpointPathForMode,
  filterModelsByMode,
  ensurePlaygroundSelectionModelLoaded,
  filterPlaygroundRouteCandidates,
  buildModelCandidateIndex,
  PLAYGROUND_MODE_LABELS,
  type PlaygroundMode,
} from './playground-mode-filter'
import { PlaygroundModelField, type RouteCandidate } from './playground-model-field'
import { PlaygroundOutputPanel } from './playground-output-panel'
import { isMultiGrantVirtualKey } from './playground-proxy-models'
import {
  buildMultiGrantTeamModelGroups,
  filterPlaygroundCandidatesForVirtualKey,
  filterPlaygroundNamesForVirtualKey,
  splitPlaygroundModelCandidatesForDisplay,
} from './playground-proxy-team'
import { PlaygroundStatusBadge } from './playground-status-badge'
import { usePlaygroundCall } from './use-playground-call'
import { usePlaygroundImageCall } from './use-playground-image'
import { usePlaygroundVideoCall } from './use-playground-video'
import { useSyncApiKeyFromVkey } from './use-sync-api-key-from-vkey'

import type { PlaygroundApiFlavor } from './types'
import type { PlaygroundModelsSnapshot } from './use-playground-filtered-models'
import type { UsePlaygroundVirtualKeyReturn } from './use-playground-virtual-key'

const DEFAULT_PROMPT = PLAYGROUND_EXAMPLE_PROMPTS.chat
const DEFAULT_PROMPT_VALUES = PLAYGROUND_EXAMPLE_PROMPT_VALUES
interface PlaygroundCardProps {
  baseUrl: string
  onModelChange?: (model: string) => void
  /** 可选凭据筛选（Guide 页与 URL 同步） */
  credentialId?: string
  onCredentialChange?: (id: string) => void
  /** Guide 页与代码示例同步试调模式（须与 onPlaygroundModeChange 成对传入） */
  playgroundMode?: PlaygroundMode
  onPlaygroundModeChange?: (mode: PlaygroundMode) => void
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
  playgroundMode: playgroundModeProp,
  onPlaygroundModeChange,
  virtualKey,
  filteredModels: {
    contextTeamId,
    credentialGroups,
    credentialById,
    candidateModels,
    routes,
    modelsLoading,
    credentialsLoading,
    credentialsEmpty,
    teamModelsLoaded,
    myModelsLoaded,
    isPersonalProxyTeam,
    onModelPickerOpenChange,
    ensureModelNameLoaded,
    usingProxyModelList,
  },
}: PlaygroundCardProps): React.JSX.Element {
  const isCredentialControlled = onCredentialChange !== undefined
  const isModeControlled = onPlaygroundModeChange !== undefined && playgroundModeProp !== undefined
  const [localCredentialId, setLocalCredentialId] = useState('')
  const [localPlaygroundMode, setLocalPlaygroundMode] = useState<PlaygroundMode>('chat')
  const credentialId = isCredentialControlled ? credentialIdProp : localCredentialId
  const playgroundMode = isModeControlled ? playgroundModeProp : localPlaygroundMode
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
  const [imageSize, setImageSize] = useState<string>(() =>
    defaultImageGenSizeForProvider(undefined)
  )
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

  const vkeyScopedModels = useMemo(
    () => filterPlaygroundCandidatesForVirtualKey(candidateModels, selectedKey?.allowed_models),
    [candidateModels, selectedKey?.allowed_models]
  )

  const modeFilteredModels = useMemo(
    () => filterModelsByMode(vkeyScopedModels, playgroundMode),
    [vkeyScopedModels, playgroundMode]
  )

  const modelsByName = useMemo(() => buildModelCandidateIndex(vkeyScopedModels), [vkeyScopedModels])

  const routeCandidates = useMemo<RouteCandidate[]>(
    () =>
      filterPlaygroundNamesForVirtualKey(
        filterPlaygroundRouteCandidates(
          routes,
          credentialId,
          vkeyScopedModels,
          playgroundMode,
          modelsByName
        ),
        selectedKey?.allowed_models
      ),
    [
      routes,
      credentialId,
      vkeyScopedModels,
      playgroundMode,
      modelsByName,
      selectedKey?.allowed_models,
    ]
  )

  const { teamCandidates, personalCandidates } = useMemo(
    () => splitPlaygroundModelCandidatesForDisplay(modeFilteredModels, isPersonalProxyTeam),
    [modeFilteredModels, isPersonalProxyTeam]
  )

  const multiGrantVkey = isMultiGrantVirtualKey(selectedKey?.granted_team_ids)
  const grantsTeamId = selectedKey?.team_id ?? ''
  const { data: vkeyGrants = [] } = useVkeyGrants(
    grantsTeamId,
    selectedKey?.id ?? '',
    multiGrantVkey && Boolean(selectedKey?.id)
  )

  const teamModelGroups = useMemo(() => {
    if (!multiGrantVkey || !usingProxyModelList) return undefined
    const candidatesForGrouping = isPersonalProxyTeam ? personalCandidates : teamCandidates
    return buildMultiGrantTeamModelGroups(candidatesForGrouping, vkeyGrants)
  }, [
    multiGrantVkey,
    usingProxyModelList,
    isPersonalProxyTeam,
    personalCandidates,
    teamCandidates,
    vkeyGrants,
  ])

  const selectedCandidate = useMemo(
    () => modeFilteredModels.find((m) => m.name === model),
    [modeFilteredModels, model]
  )

  const selectedRoute = useMemo(
    () => routeCandidates.find((r) => r.name === model),
    [routeCandidates, model]
  )

  const trimmedModel = model.trim()

  const customModelPlaceholder = multiGrantVkey
    ? '注册别名或 team-slug/model-name（跨工作区须带 slug 前缀）'
    : '输入模型别名或虚拟路由名（也可输入未列出的名称）'

  const imageGenProvider = useMemo(
    () =>
      resolvePlaygroundImageGenProvider(
        credentialById.get(credentialId)?.provider,
        selectedCandidate?.provider,
        trimmedModel
      ),
    [credentialById, credentialId, selectedCandidate?.provider, trimmedModel]
  )

  const imageGenSizes = useMemo(
    () => imageGenSizesForProvider(imageGenProvider),
    [imageGenProvider]
  )

  useEffect(() => {
    if (playgroundMode !== 'image_gen') return
    if (imageGenSizes.includes(imageSize)) return
    setImageSize(imageGenSizes[0])
  }, [playgroundMode, imageGenSizes, imageSize])

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
    if (onPlaygroundModeChange) onPlaygroundModeChange(mode)
    else setLocalPlaygroundMode(mode)
    if (!prompt.trim() || DEFAULT_PROMPT_VALUES.has(prompt)) {
      setPrompt(PLAYGROUND_EXAMPLE_PROMPTS[mode])
    }
    resetAllCalls()
  }

  const trimmedKey = apiKey.trim()
  const trimmedPrompt = prompt.trim()
  const trimmedVisionUrl = visionImageUrl.trim()

  const displayError = useMemo(() => {
    if (!error) return null
    if (playgroundMode === 'vision') {
      return withReferenceImagePayloadHint(error, trimmedVisionUrl)
    }
    if (playgroundMode === 'video_gen') {
      return withReferenceImagePayloadHint(error, videoImageUrl.trim())
    }
    return error
  }, [error, playgroundMode, trimmedVisionUrl, videoImageUrl])

  useEffect(() => {
    if (customModel || !trimmedModel) return
    ensurePlaygroundSelectionModelLoaded(
      trimmedModel,
      routeCandidates,
      ensureModelNameLoaded,
      routes
    )
  }, [customModel, trimmedModel, routeCandidates, routes, ensureModelNameLoaded])

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
    (thinkingParam === 'deepseek_v4_thinking' && apiFlavor === 'openai') ||
    (thinkingParam === 'anthropic_extended' && apiFlavor === 'anthropic')

  const thinkingSwitchInteractive = playgroundMode === 'chat' && thinkingFlavorMatch

  const isBuiltinReasoning = playgroundMode === 'chat' && thinkingParam === 'builtin_reasoning'

  const showThinkingSection =
    playgroundMode === 'chat' && (thinkingFlavorMatch || isBuiltinReasoning)

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
    // 虚拟路由以 virtual_model 名直接请求，不依赖本地分页是否已加载全部主模型
    if (selectedRoute) return true
    if (selectedCandidate) return true
    return trimmedModel.length > 0
  }, [customModel, trimmedModel, selectedRoute, selectedCandidate])

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

  /** Anthropic 兼容面使用独立的 base URL（/api/v1/anthropic/v1），其余走 OpenAI 兼容面。 */
  const effectiveBaseUrl = useMemo(
    () =>
      apiFlavor === 'anthropic' ? baseUrl.replace(/\/openai\/v1\/?$/, '/anthropic/v1') : baseUrl,
    [baseUrl, apiFlavor]
  )
  const outputEndpoint = useMemo(
    () => `${effectiveBaseUrl}${endpointPath}`,
    [effectiveBaseUrl, endpointPath]
  )
  const outputPriceRow = useMemo(() => priceByName.get(trimmedModel), [priceByName, trimmedModel])

  const handleSend = (): void => {
    const params = {
      baseUrl: effectiveBaseUrl,
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
      thinkingParam,
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
                {effectiveBaseUrl}
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
              teamId={selectedKey?.team_id ?? contextTeamId}
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
            {usingProxyModelList && credentialId ? (
              <p className="text-xs text-muted-foreground md:col-span-2 xl:col-span-3 2xl:col-span-4">
                跨 team Key 的模型列表来自 GET /v1/models，不受凭据筛选影响。
              </p>
            ) : null}
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
                teamModelGroups={teamModelGroups}
                personalCandidates={personalCandidates}
                filteredModels={modeFilteredModels}
                selectedCandidate={selectedCandidate}
                selectedRoute={selectedRoute}
                priceByName={priceByName}
                currency={GATEWAY_DISPLAY_CURRENCY}
                playgroundMode={playgroundMode}
                modelsLoading={modelsLoading}
                onOpenChange={onModelPickerOpenChange}
                customModelPlaceholder={customModelPlaceholder}
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
              label="参考图片（可选）"
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
              placeholder={PLAYGROUND_EXAMPLE_PROMPTS[playgroundMode]}
            />
          </div>

          {playgroundMode === 'image_gen' ? (
            <div className="grid gap-4 sm:grid-cols-2">
              <PlaygroundImageGenSizeField
                id={imageSizeId}
                provider={imageGenProvider}
                size={imageSize}
                onSizeChange={setImageSize}
              />
              <div className="space-y-1.5 sm:col-span-2 sm:max-w-[12rem]">
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

          {builtinThinkingHint && !showThinkingSection ? (
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
                    checked={thinkingSwitchInteractive ? thinkingEnabled : isBuiltinReasoning}
                    onCheckedChange={handleThinkingCheckedChange}
                    disabled={isBuiltinReasoning || isRunning || !thinkingSwitchInteractive}
                  />
                  <Label
                    htmlFor={thinkingId}
                    className={cn(
                      'text-sm',
                      thinkingSwitchInteractive
                        ? 'cursor-pointer'
                        : isBuiltinReasoning
                          ? 'cursor-default text-muted-foreground'
                          : 'cursor-not-allowed text-muted-foreground'
                    )}
                  >
                    思考模式
                  </Label>
                </div>
                {!thinkingSwitchInteractive && !isBuiltinReasoning && thinkingModelHint ? (
                  <p className="text-xs leading-relaxed text-muted-foreground">
                    {thinkingModelHint}
                  </p>
                ) : null}
                {isBuiltinReasoning && builtinThinkingHint ? (
                  <p className="text-xs leading-relaxed text-muted-foreground">
                    {builtinThinkingHint}
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
              error={displayError}
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
