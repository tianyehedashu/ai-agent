/**
 * AI Gateway · 调用指南
 *
 * - 在线试调（PlaygroundCard）
 * - 示例代码：OpenAI 兼容（/api/v1/openai/v1/*） + Anthropic 兼容（/api/v1/anthropic/v1/*）
 *   每个风格内支持 curl / TS / Python，流式 toggle 同步切换示例代码与典型返回默认 Tab
 * - 典型返回：4 个 Tab 横向对比（OpenAI/Anthropic × 非流式/流式），用 Badge 突出 content-type
 */

import { useCallback, useEffect, useMemo, useState, lazy, Suspense } from 'react'
import type React from 'react'

import { Link, useLocation, useSearchParams } from 'react-router-dom'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { findHomonymModels } from '@/features/gateway-keys/grants/use-team-slug-map'
import { useVkeyGrants } from '@/features/gateway-keys/grants/use-vkey-grants'
import { VkeyCrossTeamBanner } from '@/features/gateway-keys/grants/vkey-cross-team-banner'
import { usePlaygroundCredentialOptions } from '@/features/gateway-playground/playground-credential-options'
import { resolvePlaygroundVirtualKeyTeamIds } from '@/features/gateway-playground/playground-credential-summaries'
import {
  ensurePlaygroundSelectionModelLoaded,
  PLAYGROUND_MODE_LABELS,
  filterPlaygroundRouteCandidates,
  type PlaygroundMode,
} from '@/features/gateway-playground/playground-mode-filter'
import { isMultiGrantVirtualKey } from '@/features/gateway-playground/playground-proxy-models'
import { usePlaygroundFilteredModels } from '@/features/gateway-playground/use-playground-filtered-models'
import { usePlaygroundVirtualKey } from '@/features/gateway-playground/use-playground-virtual-key'
import { combineFetching } from '@/features/gateway-shared/combine-fetching'
import { GatewayRefreshButton } from '@/features/gateway-shared/gateway-refresh-button'
import { thinkingHintForModel } from '@/features/gateway-shared/thinking-param'
import {
  gatewayTeamKeysHref,
  gatewayTeamModelsHref,
  gatewayTeamRoutesHref,
} from '@/features/gateway-teams/gateway-team-paths'
import { useCopyToClipboardKeyed } from '@/hooks/use-copy-to-clipboard'
import { useGatewayMembershipTeamIds, useGatewayWorkspaceTeamId } from '@/hooks/use-gateway-team-id'
import { resolveGatewayV1BaseUrl } from '@/lib/gateway-v1-base-url'
import {
  Check,
  CheckCircle2,
  Copy,
  ExternalLink,
  FileText,
  Key,
  Network,
  Route,
  ChevronDown,
  Terminal,
  Zap,
} from '@/lib/lucide-icons'
import { cn } from '@/lib/utils'
import {
  buildCapabilityModules,
  type CapabilityGuideModule,
  type FlavorCodeTriple,
} from '@/pages/gateway/guide-capability-snippets'
import type { GuideClientIntegrationsKeyHint } from '@/pages/gateway/guide-client-integrations'
import { buildMediaModeSnippets } from '@/pages/gateway/guide-mode-snippets'
import {
  buildClientIntegrations,
  buildGuideSnippets,
  type GuideSnippets,
} from '@/pages/gateway/guide-snippets'

const PlaygroundCard = lazy(async () => {
  const mod = await import('@/features/gateway-playground/playground-card')
  return { default: mod.PlaygroundCard }
})

/** 从虚拟 Key 创建页跳转时经 React Router state 带入的明文（仅本次导航） */
export type GuideVkeyNavState = {
  vkeyPlain?: string
  vkeyId?: string
}

const GuideClientIntegrationsSection = lazy(async () => {
  const mod = await import('@/pages/gateway/guide-client-integrations')
  return { default: mod.GuideClientIntegrationsSection }
})

function GuideSectionFallback(): React.JSX.Element {
  return <div className="h-48 animate-pulse rounded-xl border border-border/60 bg-muted/30" />
}

const PLACEHOLDER_KEY = 'sk-gw-your-virtual-key'
const PLACEHOLDER_MODEL = 'claude-opus-4-7'

type ApiFlavor = 'openai' | 'anthropic'
type ResponseTab = 'openai-json' | 'openai-sse' | 'anthropic-json' | 'anthropic-sse'
type GuideResourceTab = 'clients' | 'examples' | 'reference' | 'troubleshooting'

type QuickStep = { step: number; title: string; description: string; href: string }
type TroubleshootingItem = {
  code: string
  title: string
  href: string
  linkLabel: string
  description?: string
}

function buildQuickSteps(teamId: string | null): readonly QuickStep[] {
  return [
    {
      step: 1,
      title: '创建虚拟 Key',
      description: '拿到调用凭证，后续示例会自动带入。',
      href: gatewayTeamKeysHref(teamId),
    },
    {
      step: 2,
      title: '选择模型或路由',
      description: '确认 model 名称和路由策略，避免首调 404。',
      href: gatewayTeamRoutesHref(teamId),
    },
    {
      step: 3,
      title: '复制示例并调用',
      description: '从推荐协议开始，再切换语言或流式模式。',
      href: '#examples',
    },
  ]
}

function buildTroubleshooting(
  teamId: string | null,
  multiGrantVkey: boolean
): readonly TroubleshootingItem[] {
  const modelsHref = gatewayTeamModelsHref(teamId)
  return [
    { code: '401', title: '鉴权失败', href: gatewayTeamKeysHref(teamId), linkLabel: '虚拟 Key' },
    {
      code: '404',
      title: '模型不存在',
      href: modelsHref,
      linkLabel: '模型',
      description: multiGrantVkey
        ? '确认 model 与 GET /v1/models 返回的 id 一致；跨工作区须使用 team-slug/model-name 前缀，无前缀时仅命中 Key 个人。'
        : '确认 model 注册名、Key 所属团队与模型管理一致，且模型已启用、凭据可用。',
    },
    { code: '429', title: '限流', href: modelsHref, linkLabel: '查看模型配额' },
    { code: '5xx', title: '上游失败', href: '/gateway/logs', linkLabel: '调用日志' },
  ]
}

const GUIDE_RESOURCE_TABS: readonly { value: GuideResourceTab; label: string }[] = [
  { value: 'examples', label: '代码示例' },
  { value: 'clients', label: '客户端' },
  { value: 'reference', label: '能力参考' },
  { value: 'troubleshooting', label: '排障' },
] as const

const GUIDE_CARD_CLASS = 'border-border/60 bg-card/85 shadow-none'
const GUIDE_SECTION_CLASS = 'scroll-mt-24 space-y-3'

function guideResourceTabFromHash(hash: string): GuideResourceTab | null {
  const value = hash.startsWith('#') ? hash.slice(1) : hash
  return GUIDE_RESOURCE_TABS.some((tab) => tab.value === value) ? (value as GuideResourceTab) : null
}

export default function GatewayGuidePage(): React.JSX.Element {
  const [searchParams, setSearchParams] = useSearchParams()
  const location = useLocation()
  const navState = (location.state ?? null) as GuideVkeyNavState | null
  const keyIdFromQuery = searchParams.get('key_id')
  const credentialId = searchParams.get('credentialId') ?? ''
  const preferKeyId = keyIdFromQuery ?? navState?.vkeyId ?? null
  const vkeyBootstrap = useMemo(
    () => ({
      plain: navState?.vkeyPlain ?? null,
      keyId: preferKeyId,
      preferKeyId,
    }),
    [navState?.vkeyPlain, preferKeyId]
  )

  const workspaceTeamId = useGatewayWorkspaceTeamId()
  const membershipTeamIds = useGatewayMembershipTeamIds()
  const [gatewayV1Base] = useState(resolveGatewayV1BaseUrl)
  const { byId: credentialById } = usePlaygroundCredentialOptions()
  const vkeyTeamIds = useMemo(
    () =>
      resolvePlaygroundVirtualKeyTeamIds(
        credentialId,
        credentialById,
        workspaceTeamId,
        membershipTeamIds
      ),
    [credentialId, credentialById, workspaceTeamId, membershipTeamIds]
  )

  const virtualKey = usePlaygroundVirtualKey({
    bootstrap: vkeyBootstrap,
    teamIds: vkeyTeamIds,
  })

  const selectedKey = virtualKey.selectedKey
  const multiGrantVkey = isMultiGrantVirtualKey(selectedKey?.granted_team_ids)
  const grantsTeamId = selectedKey?.team_id ?? workspaceTeamId ?? ''
  const { data: vkeyGrants = [] } = useVkeyGrants(
    grantsTeamId,
    selectedKey?.id ?? '',
    Boolean(selectedKey?.id)
  )
  const crossGrants = useMemo(() => vkeyGrants.filter((g) => !g.is_self), [vkeyGrants])
  const homonymModels = useMemo(() => findHomonymModels(vkeyGrants), [vkeyGrants])

  const playgroundFilteredModels = usePlaygroundFilteredModels({
    credentialId,
    includeRoutes: true,
    proxyTeamId: selectedKey?.team_id ?? null,
    proxyVkeyPlain: virtualKey.plain,
    proxyVkeyBaseUrl: gatewayV1Base,
    proxyVkeyId: selectedKey?.id ?? null,
    multiGrantVkey,
  })
  const {
    credentialsLoading,
    candidateModels: guideModelCandidates,
    routes: guideRoutes,
    ensureModelNameLoaded,
    isRefreshing: playgroundModelsRefreshing,
    refreshAll: refreshPlaygroundModels,
    proxyModelsError,
  } = playgroundFilteredModels
  const { plain: revealedKey, isRevealing } = virtualKey
  const [activeModel, setActiveModel] = useState<string>(PLACEHOLDER_MODEL)
  const [playgroundMode, setPlaygroundMode] = useState<PlaygroundMode>('chat')
  const [apiFlavor, setApiFlavor] = useState<ApiFlavor>('openai')
  const [exampleStream, setExampleStream] = useState(true)
  const [responseTab, setResponseTab] = useState<ResponseTab>('openai-sse')
  const [resourceTab, setResourceTab] = useState<GuideResourceTab>(
    () => guideResourceTabFromHash(location.hash) ?? 'examples'
  )

  const guideRouteCandidates = useMemo(
    () => filterPlaygroundRouteCandidates(guideRoutes, '', guideModelCandidates, playgroundMode),
    [guideRoutes, guideModelCandidates, playgroundMode]
  )

  const displayKey = revealedKey ?? PLACEHOLDER_KEY
  const clientIntegrationsKeyHint: GuideClientIntegrationsKeyHint = revealedKey
    ? 'revealed'
    : isRevealing
      ? 'revealing'
      : 'placeholder'

  const snippets = useMemo(
    () =>
      buildGuideSnippets(gatewayV1Base, displayKey, activeModel || PLACEHOLDER_MODEL, {
        multiGrantVkey,
      }),
    [gatewayV1Base, displayKey, activeModel, multiGrantVkey]
  )
  const clientIntegrations = useMemo(
    () =>
      buildClientIntegrations(
        gatewayV1Base,
        displayKey,
        activeModel || PLACEHOLDER_MODEL,
        snippets,
        { multiGrantVkey }
      ),
    [gatewayV1Base, displayKey, activeModel, snippets, multiGrantVkey]
  )

  const openResourceTab = useCallback((tab: GuideResourceTab): void => {
    setResourceTab(tab)
    requestAnimationFrame(() => {
      scrollToGuideSection('#resources', `#${tab}`)
    })
  }, [])

  const handleResourceTabChange = useCallback((value: string): void => {
    const tab = guideResourceTabFromHash(value)
    if (!tab) return
    setResourceTab(tab)
    window.history.replaceState(null, '', `#${tab}`)
  }, [])

  useEffect(() => {
    const tabFromHash = guideResourceTabFromHash(location.hash)
    const nextTab = tabFromHash ?? (keyIdFromQuery ? 'clients' : null)
    if (!nextTab) {
      if (location.hash !== '#playground') return
      const frame = requestAnimationFrame(() => {
        scrollToGuideSection('#playground')
      })
      return () => {
        cancelAnimationFrame(frame)
      }
    }
    setResourceTab(nextTab)
    const frame = requestAnimationFrame(() => {
      scrollToGuideSection('#resources', `#${nextTab}`)
    })
    return () => {
      cancelAnimationFrame(frame)
    }
  }, [location.hash, keyIdFromQuery])

  const capabilityModules = useMemo(
    () => buildCapabilityModules(gatewayV1Base, displayKey, activeModel || PLACEHOLDER_MODEL),
    [gatewayV1Base, displayKey, activeModel]
  )

  const mediaModeSnippets = useMemo(() => {
    if (playgroundMode === 'chat') return null
    return buildMediaModeSnippets(
      gatewayV1Base,
      displayKey,
      activeModel || PLACEHOLDER_MODEL,
      playgroundMode
    )
  }, [gatewayV1Base, displayKey, activeModel, playgroundMode])

  const handlePlaygroundRefresh = useCallback((): void => {
    refreshPlaygroundModels()
    virtualKey.refreshKeys()
  }, [refreshPlaygroundModels, virtualKey])

  useEffect(() => {
    const name = activeModel || PLACEHOLDER_MODEL
    if (name === PLACEHOLDER_MODEL) return
    ensurePlaygroundSelectionModelLoaded(
      name,
      guideRouteCandidates,
      ensureModelNameLoaded,
      guideRoutes
    )
  }, [activeModel, guideRouteCandidates, guideRoutes, ensureModelNameLoaded])

  useEffect(() => {
    if (!credentialId || credentialsLoading) return
    if (!credentialById.has(credentialId)) {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev)
          next.delete('credentialId')
          return next
        },
        { replace: true }
      )
    }
  }, [credentialId, credentialById, credentialsLoading, setSearchParams])

  const activeModelCapabilities = useMemo(() => {
    const name = activeModel || PLACEHOLDER_MODEL
    return guideModelCandidates.find((m) => m.name === name)?.selector_capabilities
  }, [guideModelCandidates, activeModel])

  const thinkingModelHint = useMemo(
    () =>
      thinkingHintForModel(activeModel || PLACEHOLDER_MODEL, apiFlavor, activeModelCapabilities, {
        allowNameFallback: guideModelCandidates.length === 0,
      }),
    [activeModel, apiFlavor, activeModelCapabilities, guideModelCandidates.length]
  )
  const [copy, copiedKey] = useCopyToClipboardKeyed<string>()
  const handleCopy = useCallback(
    (key: string, text: string) => {
      void copy(text, key)
    },
    [copy]
  )
  const handlePlaygroundModeChange = useCallback((mode: PlaygroundMode) => {
    setPlaygroundMode(mode)
  }, [])
  const handlePlaygroundModelChange = useCallback((next: string) => {
    if (!next) {
      setActiveModel(PLACEHOLDER_MODEL)
      return
    }
    setActiveModel(next)
  }, [])
  const handleCredentialChange = useCallback(
    (id: string) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev)
          if (id) next.set('credentialId', id)
          else next.delete('credentialId')
          return next
        },
        { replace: true }
      )
    },
    [setSearchParams]
  )

  // 示例流式 / API 风格变化时，把典型返回 Tab 默认联动到对应组合，但仍允许独立切换
  useEffect(() => {
    setResponseTab(`${apiFlavor}-${exampleStream ? 'sse' : 'json'}` as ResponseTab)
  }, [apiFlavor, exampleStream])

  const quickSteps = useMemo(() => buildQuickSteps(workspaceTeamId), [workspaceTeamId])
  const troubleshooting = useMemo(
    () => buildTroubleshooting(workspaceTeamId, multiGrantVkey),
    [workspaceTeamId, multiGrantVkey]
  )
  const awaitingCrossTeamReveal = multiGrantVkey && !revealedKey
  const proxyModelsErrorMessage = proxyModelsError?.message ?? null

  const handleRetryProxyModels = useCallback((): void => {
    refreshPlaygroundModels()
  }, [refreshPlaygroundModels])

  return (
    <div className="w-full max-w-[1500px] px-5 py-5 lg:px-7 xl:px-8">
      <GuideHero
        baseUrl={gatewayV1Base}
        keyHint={clientIntegrationsKeyHint}
        modeLabel={PLAYGROUND_MODE_LABELS[playgroundMode]}
        model={activeModel || PLACEHOLDER_MODEL}
        onOpenClients={() => {
          openResourceTab('clients')
        }}
        onOpenExamples={() => {
          openResourceTab('examples')
        }}
      />

      <div className="mt-6">
        <div className="space-y-8">
          <section aria-labelledby="quick-start-heading" className="scroll-mt-24">
            <h2 id="quick-start-heading" className="sr-only">
              先跑通一次调用
            </h2>
            <div className="grid gap-2 2xl:grid-cols-3">
              {quickSteps.map((item) => (
                <QuickStepItem key={item.step} item={item} onOpenResourceTab={openResourceTab} />
              ))}
            </div>
          </section>

          <section
            id="playground"
            aria-labelledby="playground-heading"
            className={GUIDE_SECTION_CLASS}
          >
            <GuideSectionHeader
              id="playground-heading"
              title="在线试调"
              description="先在页面里确认 Key、模型和能力都可用，再复制下方示例到客户端。"
              actions={
                <GatewayRefreshButton
                  isFetching={combineFetching(
                    playgroundModelsRefreshing,
                    virtualKey.isRefreshingKeys
                  )}
                  ariaLabel="刷新试调数据"
                  onRefresh={handlePlaygroundRefresh}
                />
              }
            />
            {multiGrantVkey ? (
              <VkeyCrossTeamBanner
                visible
                crossTeamCount={crossGrants.length}
                homonymModels={homonymModels}
                awaitingReveal={awaitingCrossTeamReveal}
                proxyModelsError={proxyModelsErrorMessage}
                onRetryProxyModels={handleRetryProxyModels}
                keysHrefTeamId={workspaceTeamId}
              />
            ) : null}
            <Suspense fallback={<GuideSectionFallback />}>
              <PlaygroundCard
                baseUrl={gatewayV1Base}
                title="请求配置"
                onModelChange={handlePlaygroundModelChange}
                playgroundMode={playgroundMode}
                onPlaygroundModeChange={handlePlaygroundModeChange}
                credentialId={credentialId}
                onCredentialChange={handleCredentialChange}
                virtualKey={virtualKey}
                filteredModels={playgroundFilteredModels}
              />
            </Suspense>
          </section>

          <section
            id="resources"
            aria-labelledby="resources-heading"
            className={GUIDE_SECTION_CLASS}
          >
            <GuideSectionHeader
              id="resources-heading"
              title="接入资料"
              description="客户端、代码示例、能力参考和排障收在同一处，按当前试调配置自动变化。"
            />
            <Tabs value={resourceTab} onValueChange={handleResourceTabChange} className="space-y-4">
              <TabsList className="grid h-auto w-full grid-cols-2 gap-1 p-1 lg:w-fit lg:grid-cols-4">
                {GUIDE_RESOURCE_TABS.map((tab) => (
                  <TabsTrigger key={tab.value} value={tab.value} className="h-8 px-3 text-xs">
                    {tab.label}
                  </TabsTrigger>
                ))}
              </TabsList>

              <TabsContent value="examples" id="examples" className="mt-0">
                <Card className={GUIDE_CARD_CLASS}>
                  <CardHeader className="pb-4">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                      <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                        <span>当前试调</span>
                        <Badge variant="secondary" className="font-normal">
                          {PLAYGROUND_MODE_LABELS[playgroundMode]}
                        </Badge>
                      </div>
                      {playgroundMode === 'chat' ? (
                        <div className="flex w-fit items-center gap-2 rounded-lg border border-border/70 bg-card/80 px-3 py-2">
                          <Zap
                            className={cn(
                              'h-4 w-4',
                              exampleStream ? 'text-amber-500' : 'text-muted-foreground'
                            )}
                            aria-hidden="true"
                          />
                          <Label htmlFor="example-stream" className="cursor-pointer text-sm">
                            SSE
                          </Label>
                          <Switch
                            id="example-stream"
                            checked={exampleStream}
                            onCheckedChange={setExampleStream}
                          />
                        </div>
                      ) : null}
                    </div>
                  </CardHeader>
                  <CardContent className="pt-0">
                    {playgroundMode === 'chat' ? (
                      <Tabs
                        value={apiFlavor}
                        onValueChange={(v) => {
                          setApiFlavor(v as ApiFlavor)
                        }}
                      >
                        <TabsList>
                          <TabsTrigger value="openai">OpenAI 兼容</TabsTrigger>
                          <TabsTrigger value="anthropic">Anthropic 兼容</TabsTrigger>
                        </TabsList>

                        <TabsContent value="openai" className="space-y-4 pt-3">
                          <EndpointBadge
                            endpoint={snippets.openai.endpoint}
                            mode={exampleStream ? 'stream' : 'json'}
                            copyKey="openaiEndpoint"
                            copied={copiedKey === 'openaiEndpoint'}
                            onCopy={handleCopy}
                          />
                          <FlavorExamples
                            curl={exampleStream ? snippets.openai.curlStream : snippets.openai.curl}
                            ts={exampleStream ? snippets.openai.tsStream : snippets.openai.ts}
                            py={exampleStream ? snippets.openai.pyStream : snippets.openai.py}
                            keyPrefix={`openai-${exampleStream ? 'stream' : 'json'}`}
                            copiedKey={copiedKey}
                            onCopy={handleCopy}
                          />
                        </TabsContent>

                        <TabsContent value="anthropic" className="space-y-4 pt-3">
                          <EndpointBadge
                            endpoint={snippets.anthropic.endpoint}
                            mode={exampleStream ? 'stream' : 'json'}
                            copyKey="anthropicEndpoint"
                            copied={copiedKey === 'anthropicEndpoint'}
                            onCopy={handleCopy}
                          />
                          <FlavorExamples
                            curl={
                              exampleStream
                                ? snippets.anthropic.curlStream
                                : snippets.anthropic.curl
                            }
                            ts={exampleStream ? snippets.anthropic.tsStream : snippets.anthropic.ts}
                            py={exampleStream ? snippets.anthropic.pyStream : snippets.anthropic.py}
                            keyPrefix={`anthropic-${exampleStream ? 'stream' : 'json'}`}
                            copiedKey={copiedKey}
                            onCopy={handleCopy}
                          />
                        </TabsContent>
                      </Tabs>
                    ) : mediaModeSnippets ? (
                      <div className="space-y-4">
                        {mediaModeSnippets.hint ? (
                          <p className="rounded-lg border border-info/20 bg-info/5 px-3 py-2 text-sm text-muted-foreground">
                            {mediaModeSnippets.hint}
                            <Link
                              to={gatewayTeamModelsHref(workspaceTeamId)}
                              className="ml-1 text-primary underline-offset-4 hover:underline"
                            >
                              查看模型
                            </Link>
                          </p>
                        ) : null}
                        <EndpointBadge
                          endpoint={mediaModeSnippets.endpoint}
                          mode="json"
                          copyKey="mediaEndpoint"
                          copied={copiedKey === 'mediaEndpoint'}
                          onCopy={handleCopy}
                        />
                        <FlavorExamples
                          curl={mediaModeSnippets.curl}
                          ts={mediaModeSnippets.ts}
                          py={mediaModeSnippets.py}
                          keyPrefix={`media-${playgroundMode}`}
                          copiedKey={copiedKey}
                          onCopy={handleCopy}
                        />
                      </div>
                    ) : null}
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="clients" id="clients" className="mt-0">
                <Suspense fallback={<GuideSectionFallback />}>
                  <GuideClientIntegrationsSection
                    clients={clientIntegrations}
                    copiedKey={copiedKey}
                    onCopy={handleCopy}
                    keyHint={clientIntegrationsKeyHint}
                  />
                </Suspense>
              </TabsContent>

              <TabsContent value="reference" id="reference" className="mt-0">
                <Card className={GUIDE_CARD_CLASS}>
                  <CardContent className="space-y-4 p-5">
                    <GuideReferenceSection title="按能力查看示例" defaultOpen>
                      <p className="mb-3 text-sm text-muted-foreground">
                        图片生成、视频生成的 curl 示例见
                        <button
                          type="button"
                          className="mx-1 text-primary underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                          onClick={() => {
                            setResourceTab('examples')
                            window.history.replaceState(null, '', '#examples')
                          }}
                        >
                          代码示例
                        </button>
                        ，随在线试调 Tab 切换。
                      </p>
                      <div id="capabilities" className="scroll-mt-24 space-y-3">
                        {capabilityModules.map((mod) => (
                          <CapabilityGuideCard
                            key={mod.id}
                            module={mod}
                            apiFlavor={apiFlavor}
                            modelHint={mod.id === 'thinking' ? thinkingModelHint : null}
                            copiedKey={copiedKey}
                            onCopy={handleCopy}
                          />
                        ))}
                      </div>
                    </GuideReferenceSection>

                    <GuideReferenceSection title="典型返回">
                      <ResponseExamples
                        responseTab={responseTab}
                        setResponseTab={setResponseTab}
                        snippets={snippets}
                        copiedKey={copiedKey}
                        onCopy={handleCopy}
                      />
                    </GuideReferenceSection>

                    <GuideReferenceSection title="查询可用模型">
                      <CodeExampleCard
                        title="curl"
                        icon={Terminal}
                        code={snippets.modelsCurl}
                        copyKey="modelsCurl"
                        copied={copiedKey === 'modelsCurl'}
                        onCopy={handleCopy}
                        embedded
                      />
                    </GuideReferenceSection>
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="troubleshooting" id="troubleshooting" className="mt-0">
                <div className="grid gap-4 md:grid-cols-2">
                  {troubleshooting.map((item) => (
                    <TroubleshootingCard key={item.code} item={item} />
                  ))}
                </div>
              </TabsContent>
            </Tabs>
          </section>
        </div>
      </div>
    </div>
  )
}

function GuideHero({
  baseUrl,
  keyHint,
  modeLabel,
  model,
  onOpenClients,
  onOpenExamples,
}: Readonly<{
  baseUrl: string
  keyHint: GuideClientIntegrationsKeyHint
  modeLabel: string
  model: string
  onOpenClients: () => void
  onOpenExamples: () => void
}>): React.JSX.Element {
  const keyStatus =
    keyHint === 'revealed'
      ? '已载入真实 Key'
      : keyHint === 'revealing'
        ? '正在载入 Key'
        : '占位示例'

  return (
    <section className="border-b border-border/60 pb-4">
      <div className="flex flex-col gap-4 2xl:flex-row 2xl:items-start 2xl:justify-between">
        <div className="min-w-0 max-w-4xl">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-primary/80">
            AI Gateway
          </p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight text-foreground">调用指南</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
            从一次可运行的请求开始：选择虚拟 Key
            和模型，在线试调确认可用，再把同一套配置复制到客户端或 SDK。
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Button asChild>
              <a
                href="#examples"
                onClick={(event) => {
                  event.preventDefault()
                  onOpenExamples()
                }}
              >
                查看代码示例
              </a>
            </Button>
            <Button variant="outline" asChild>
              <a
                href="#clients"
                onClick={(event) => {
                  event.preventDefault()
                  onOpenClients()
                }}
              >
                客户端配置
              </a>
            </Button>
          </div>
        </div>

        <div className="grid min-w-0 gap-2 sm:grid-cols-3 2xl:w-[34rem]">
          <GuideHeroSignal icon={Key} label="Key" value={keyStatus} />
          <GuideHeroSignal icon={Network} label="模型" value={model} code />
          <GuideHeroSignal icon={Route} label="模式" value={modeLabel} />
        </div>
      </div>
      <div className="mt-3 flex min-w-0 items-center gap-2 rounded-lg border border-border/60 bg-card/60 px-3 py-2 text-xs text-muted-foreground">
        <span className="font-medium text-foreground">Base URL</span>
        <span className="min-w-0 truncate font-mono" translate="no">
          {baseUrl}
        </span>
      </div>
    </section>
  )
}

function GuideHeroSignal({
  icon: Icon,
  label,
  value,
  code,
}: Readonly<{
  icon: React.ComponentType<{ className?: string }>
  label: string
  value: string
  code?: boolean
}>): React.JSX.Element {
  return (
    <div className="flex min-w-0 items-center gap-2 rounded-lg border border-border/60 bg-card/60 px-2.5 py-2">
      <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
        <Icon className="h-4 w-4" aria-hidden="true" />
      </div>
      <div className="min-w-0">
        <p className="text-[10px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
          {label}
        </p>
        <p
          className={cn('mt-0.5 truncate text-sm font-medium text-foreground', code && 'font-mono')}
          translate={code ? 'no' : undefined}
        >
          {value}
        </p>
      </div>
    </div>
  )
}

function GuideSectionHeader({
  id,
  title,
  description,
  actions,
}: Readonly<{
  id: string
  title: string
  description: string
  actions?: React.ReactNode
}>): React.JSX.Element {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div className="max-w-3xl">
        <h2 id={id} className="text-lg font-semibold tracking-tight text-foreground">
          {title}
        </h2>
        <p className="mt-1 text-sm leading-6 text-muted-foreground">{description}</p>
      </div>
      {actions ? <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div> : null}
    </div>
  )
}

function scrollToGuideSection(href: string, historyHref = href): void {
  const target = document.getElementById(href.slice(1))
  if (!target) return
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  const behavior: ScrollBehavior = reducedMotion ? 'auto' : 'smooth'
  const scrollParent = findScrollableParent(target)

  if (scrollParent) {
    const parentRect = scrollParent.getBoundingClientRect()
    const targetRect = target.getBoundingClientRect()
    scrollParent.scrollTo({
      top: scrollParent.scrollTop + targetRect.top - parentRect.top - 24,
      behavior,
    })
  } else {
    target.scrollIntoView({ behavior, block: 'start' })
  }

  window.history.replaceState(null, '', historyHref)
}

function findScrollableParent(element: HTMLElement): HTMLElement | null {
  let current = element.parentElement
  while (current) {
    const style = window.getComputedStyle(current)
    const canScroll = /(auto|scroll)/.test(style.overflowY)
    if (canScroll && current.scrollHeight > current.clientHeight) {
      return current
    }
    current = current.parentElement
  }
  return null
}

function QuickStepItem({
  item,
  onOpenResourceTab,
}: Readonly<{
  item: QuickStep
  onOpenResourceTab: (tab: GuideResourceTab) => void
}>): React.JSX.Element {
  const content = (
    <div className="group flex h-full min-w-0 items-start gap-3 rounded-lg border border-border/60 bg-card/70 p-3 transition-colors hover:border-primary/30 hover:bg-card">
      <div className="flex shrink-0 items-center gap-3">
        <Badge
          variant="secondary"
          className="h-7 w-7 justify-center rounded-full border border-primary/20 bg-primary/10 p-0 text-primary"
        >
          {item.step}
        </Badge>
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold">{item.title}</p>
        <p className="mt-1 hidden text-xs leading-5 text-muted-foreground 2xl:block">
          {item.description}
        </p>
      </div>
      {item.href.startsWith('#') ? (
        <CheckCircle2 className="mt-1 h-4 w-4 shrink-0 text-success" aria-hidden="true" />
      ) : (
        <ExternalLink
          className="mt-1 h-4 w-4 shrink-0 text-muted-foreground transition-colors group-hover:text-primary"
          aria-hidden="true"
        />
      )}
    </div>
  )

  if (item.href.startsWith('#')) {
    const resourceTab = guideResourceTabFromHash(item.href)
    return (
      <a
        href={item.href}
        className="rounded-lg underline-offset-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        onClick={(event) => {
          if (!resourceTab) return
          event.preventDefault()
          onOpenResourceTab(resourceTab)
        }}
      >
        {content}
      </a>
    )
  }

  return (
    <Link
      to={item.href}
      className="rounded-lg underline-offset-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      {content}
    </Link>
  )
}

function GuideReferenceSection({
  title,
  children,
  defaultOpen,
}: Readonly<{
  title: string
  children: React.ReactNode
  defaultOpen?: boolean
}>): React.JSX.Element {
  return (
    <Collapsible
      defaultOpen={defaultOpen}
      className="overflow-hidden rounded-xl border bg-background/45"
    >
      <CollapsibleTrigger className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left text-sm font-medium hover:bg-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring [&[data-state=open]>svg]:rotate-180">
        {title}
        <ChevronDown
          className="h-4 w-4 shrink-0 text-muted-foreground transition-transform"
          aria-hidden="true"
        />
      </CollapsibleTrigger>
      <CollapsibleContent className="border-t p-4">{children}</CollapsibleContent>
    </Collapsible>
  )
}

function ResponseExamples({
  responseTab,
  setResponseTab,
  snippets,
  copiedKey,
  onCopy,
}: Readonly<{
  responseTab: ResponseTab
  setResponseTab: (tab: ResponseTab) => void
  snippets: GuideSnippets
  copiedKey: string | null
  onCopy: (key: string, text: string) => void
}>): React.JSX.Element {
  return (
    <Tabs
      value={responseTab}
      onValueChange={(v) => {
        setResponseTab(v as ResponseTab)
      }}
    >
      <TabsList className="flex h-auto flex-wrap gap-1">
        <ResponseTabTrigger value="openai-json" flavor="OpenAI" mode="json" />
        <ResponseTabTrigger value="openai-sse" flavor="OpenAI" mode="sse" />
        <ResponseTabTrigger value="anthropic-json" flavor="Anthropic" mode="json" />
        <ResponseTabTrigger value="anthropic-sse" flavor="Anthropic" mode="sse" />
      </TabsList>
      <TabsContent value="openai-json">
        <ResponseExample
          code={snippets.openai.responseJson}
          copyKey="openaiResponseJson"
          copied={copiedKey === 'openaiResponseJson'}
          onCopy={onCopy}
        />
      </TabsContent>
      <TabsContent value="openai-sse">
        <ResponseExample
          code={snippets.openai.responseSse}
          copyKey="openaiResponseSse"
          copied={copiedKey === 'openaiResponseSse'}
          onCopy={onCopy}
        />
      </TabsContent>
      <TabsContent value="anthropic-json">
        <ResponseExample
          code={snippets.anthropic.responseJson}
          copyKey="anthropicResponseJson"
          copied={copiedKey === 'anthropicResponseJson'}
          onCopy={onCopy}
        />
      </TabsContent>
      <TabsContent value="anthropic-sse">
        <ResponseExample
          code={snippets.anthropic.responseSse}
          copyKey="anthropicResponseSse"
          copied={copiedKey === 'anthropicResponseSse'}
          onCopy={onCopy}
        />
      </TabsContent>
    </Tabs>
  )
}

function TroubleshootingCard({ item }: Readonly<{ item: TroubleshootingItem }>): React.JSX.Element {
  const description = 'description' in item ? item.description : undefined
  return (
    <div className="rounded-xl border border-border/60 bg-card/90 p-4 shadow-sm shadow-black/[0.03] dark:shadow-black/20">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2 text-sm font-medium">
            <Badge variant="outline" className="font-mono" translate="no">
              {item.code}
            </Badge>
            {item.title}
          </div>
          {description ? (
            <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{description}</p>
          ) : null}
        </div>
        <Link
          to={item.href}
          className="shrink-0 text-sm font-medium text-primary underline-offset-4 hover:underline"
        >
          {item.linkLabel}
        </Link>
      </div>
    </div>
  )
}

function CapabilityGuideCard({
  module,
  apiFlavor,
  modelHint,
  copiedKey,
  onCopy,
}: Readonly<{
  module: CapabilityGuideModule
  apiFlavor: ApiFlavor
  modelHint?: string | null
  copiedKey: string | null
  onCopy: (key: string, text: string) => void
}>): React.JSX.Element {
  const snippets: FlavorCodeTriple = apiFlavor === 'openai' ? module.openai : module.anthropic
  const keyPrefix = `cap-${module.id}-${apiFlavor}`

  return (
    <Collapsible
      defaultOpen={module.id === 'tools'}
      className="overflow-hidden rounded-lg border bg-card/60"
    >
      <CollapsibleTrigger className="flex w-full items-start justify-between gap-3 px-4 py-3 text-left hover:bg-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring [&[data-state=open]>svg]:rotate-180">
        <p className="min-w-0 text-sm font-medium">{module.title}</p>
        <ChevronDown
          className="mt-1 h-4 w-4 shrink-0 text-muted-foreground transition-transform"
          aria-hidden="true"
        />
      </CollapsibleTrigger>
      <CollapsibleContent className="space-y-4 border-t p-4">
        {modelHint ? (
          <p className="rounded-md border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-xs leading-relaxed text-muted-foreground">
            {modelHint}
          </p>
        ) : null}
        <FlavorExamples
          curl={snippets.curl}
          ts={snippets.ts}
          py={snippets.py}
          keyPrefix={keyPrefix}
          copiedKey={copiedKey}
          onCopy={onCopy}
        />
      </CollapsibleContent>
    </Collapsible>
  )
}

function EndpointBadge({
  endpoint,
  mode,
  copyKey,
  copied,
  onCopy,
}: Readonly<{
  endpoint: string
  mode: 'json' | 'stream'
  copyKey: string
  copied: boolean
  onCopy: (key: string, text: string) => void
}>): React.JSX.Element {
  const [method, ...pathParts] = endpoint.split(' ')
  const path = pathParts.join(' ')
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-xl border border-border/70 bg-muted/25 px-3 py-2.5 text-xs">
      <Badge variant="secondary" className="shrink-0 font-mono">
        {method}
      </Badge>
      <span className="min-w-[12rem] flex-1 break-all font-mono text-foreground/90" translate="no">
        {path}
      </span>
      <Badge
        variant="outline"
        className={cn(
          'shrink-0 font-mono',
          mode === 'stream' && 'border-amber-500/40 text-amber-600'
        )}
      >
        {mode === 'stream' ? 'SSE' : 'JSON'}
      </Badge>
      <CopyButton
        copied={copied}
        label="复制端点"
        compact
        onCopy={() => {
          onCopy(copyKey, endpoint)
        }}
      />
    </div>
  )
}

function FlavorExamples({
  curl,
  ts,
  py,
  keyPrefix,
  copiedKey,
  onCopy,
}: Readonly<{
  curl: string
  ts: string
  py: string
  keyPrefix: string
  copiedKey: string | null
  onCopy: (key: string, text: string) => void
}>): React.JSX.Element {
  const curlKey = `${keyPrefix}-curl`
  const tsKey = `${keyPrefix}-ts`
  const pyKey = `${keyPrefix}-py`
  return (
    <Tabs defaultValue="curl" className="space-y-2">
      <TabsList className="h-auto flex-wrap gap-1">
        <TabsTrigger value="curl" className="h-7 px-3 text-xs">
          curl
        </TabsTrigger>
        <TabsTrigger value="ts" className="h-7 px-3 text-xs">
          TypeScript
        </TabsTrigger>
        <TabsTrigger value="py" className="h-7 px-3 text-xs">
          Python
        </TabsTrigger>
      </TabsList>
      <TabsContent value="curl">
        <CodeExampleCard
          title="curl"
          icon={Terminal}
          code={curl}
          copyKey={curlKey}
          copied={copiedKey === curlKey}
          onCopy={onCopy}
          embedded
        />
      </TabsContent>
      <TabsContent value="ts">
        <CodeExampleCard
          title="TypeScript SDK"
          code={ts}
          copyKey={tsKey}
          copied={copiedKey === tsKey}
          onCopy={onCopy}
          embedded
        />
      </TabsContent>
      <TabsContent value="py">
        <CodeExampleCard
          title="Python SDK"
          code={py}
          copyKey={pyKey}
          copied={copiedKey === pyKey}
          onCopy={onCopy}
          embedded
        />
      </TabsContent>
    </Tabs>
  )
}

function ResponseTabTrigger({
  value,
  flavor,
  mode,
}: Readonly<{
  value: ResponseTab
  flavor: 'OpenAI' | 'Anthropic'
  mode: 'json' | 'sse'
}>): React.JSX.Element {
  return (
    <TabsTrigger value={value} className="h-9 gap-1.5 px-3 text-xs">
      {mode === 'sse' ? (
        <Zap className="h-3.5 w-3.5 text-amber-500" aria-hidden="true" />
      ) : (
        <FileText className="h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" />
      )}
      <span className="font-medium">{flavor}</span>
      <span className="text-muted-foreground">·</span>
      <span>{mode === 'sse' ? '流式' : '非流式'}</span>
    </TabsTrigger>
  )
}

function ResponseExample({
  code,
  copyKey,
  copied,
  onCopy,
}: Readonly<{
  code: string
  copyKey: string
  copied: boolean
  onCopy: (key: string, text: string) => void
}>): React.JSX.Element {
  return (
    <div>
      <CodeExampleCard
        title="响应"
        code={code}
        copyKey={copyKey}
        copied={copied}
        onCopy={onCopy}
        embedded
      />
    </div>
  )
}

function CodeExampleCard({
  title,
  code,
  copyKey,
  copied,
  onCopy,
  icon: Icon = Terminal,
  embedded,
}: Readonly<{
  title: string
  code: string
  copyKey: string
  copied: boolean
  onCopy: (key: string, text: string) => void
  icon?: React.ComponentType<{ className?: string }>
  embedded?: boolean
}>): React.JSX.Element {
  const inner = (
    <div className="relative">
      <div className="absolute right-2 top-2 z-10">
        <CopyButton
          copied={copied}
          label={`复制 ${title}`}
          compact={embedded}
          onCopy={() => {
            onCopy(copyKey, code)
          }}
        />
      </div>
      <pre className="max-h-[32rem] overflow-auto rounded-xl border border-border/70 bg-muted/35 p-4 pr-24 text-xs leading-relaxed shadow-inner shadow-black/[0.02]">
        <code translate="no">{code}</code>
      </pre>
    </div>
  )

  if (embedded) {
    return inner
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="flex items-center gap-2 text-sm font-medium">
          <Icon className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-0">{inner}</CardContent>
    </Card>
  )
}

function CopyButton({
  copied,
  label,
  compact,
  onCopy,
}: Readonly<{
  copied: boolean
  label: string
  compact?: boolean
  onCopy: () => void
}>): React.JSX.Element {
  if (compact) {
    return (
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="h-7 w-7 shrink-0"
        aria-label={label}
        onClick={onCopy}
      >
        {copied ? (
          <Check className="h-3.5 w-3.5" aria-hidden="true" />
        ) : (
          <Copy className="h-3.5 w-3.5" aria-hidden="true" />
        )}
      </Button>
    )
  }
  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      className="h-8 gap-1.5"
      aria-label={label}
      onClick={onCopy}
    >
      {copied ? (
        <>
          <Check className="h-3.5 w-3.5" aria-hidden="true" />
          已复制
        </>
      ) : (
        <>
          <Copy className="h-3.5 w-3.5" aria-hidden="true" />
          复制
        </>
      )}
    </Button>
  )
}
