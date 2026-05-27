/**
 * AI Gateway · 调用指南
 *
 * - 在线试调（PlaygroundCard）
 * - 示例代码：OpenAI 兼容（/api/v1/openai/v1/*） + Anthropic 兼容（/api/v1/anthropic/v1/*）
 *   每个风格内支持 curl / TS / Python，流式 toggle 同步切换示例代码与典型返回默认 Tab
 * - 典型返回：4 个 Tab 横向对比（OpenAI/Anthropic × 非流式/流式），用 Badge 突出 content-type
 */

import { memo, useCallback, useEffect, useMemo, useState, lazy, Suspense } from 'react'
import type React from 'react'

import { Link, useLocation, useSearchParams } from 'react-router-dom'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { resolvePlaygroundVirtualKeyTeamIds } from '@/features/gateway-playground/playground-credential-summaries'
import {
  ensurePlaygroundSelectionModelLoaded,
  PLAYGROUND_MODE_LABELS,
  filterPlaygroundRouteCandidates,
  type PlaygroundMode,
} from '@/features/gateway-playground/playground-mode-filter'
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
import { Check, Copy, ExternalLink, FileText, ChevronDown, Terminal, Zap } from '@/lib/lucide-icons'
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

type QuickStep = { step: number; title: string; href: string }
type TroubleshootingItem = {
  code: string
  title: string
  href: string
  linkLabel: string
  description?: string
}

function buildQuickSteps(teamId: string | null): readonly QuickStep[] {
  return [
    { step: 1, title: '创建虚拟 Key', href: gatewayTeamKeysHref(teamId) },
    { step: 2, title: '选择模型或路由', href: gatewayTeamRoutesHref(teamId) },
    { step: 3, title: '复制示例并调用', href: '#examples' },
  ]
}

function buildTroubleshooting(teamId: string | null): readonly TroubleshootingItem[] {
  const modelsHref = gatewayTeamModelsHref(teamId)
  return [
    { code: '401', title: '鉴权失败', href: gatewayTeamKeysHref(teamId), linkLabel: '虚拟 Key' },
    {
      code: '404',
      title: '模型不存在',
      href: modelsHref,
      linkLabel: '模型',
      description: '确认 model 注册名、Key 所属团队与模型管理一致，且模型已启用、凭据可用。',
    },
    { code: '429', title: '限流', href: modelsHref, linkLabel: '查看模型配额' },
    { code: '5xx', title: '上游失败', href: '/gateway/logs', linkLabel: '调用日志' },
  ]
}

const GUIDE_NAV_ITEMS = [
  ['#playground', '在线试调'],
  ['#clients', '客户端集成'],
  ['#examples', '代码示例'],
  ['#reference', '能力参考'],
  ['#troubleshooting', '异常排查'],
] as const

const GUIDE_CARD_CLASS = 'border-border/60 bg-background shadow-sm'

const GUIDE_NAV_IDS = GUIDE_NAV_ITEMS.map(([href]) => href.slice(1))

/**
 * scroll-spy：基于 IntersectionObserver 监听各 section，
 * 选取最靠近视口上沿的可见 section 作为当前位置。
 */
function useActiveGuideAnchor(): string {
  const [active, setActive] = useState<string>(GUIDE_NAV_ITEMS[0][0])

  useEffect(() => {
    const targets = GUIDE_NAV_IDS.map((id) => document.getElementById(id)).filter(
      (el): el is HTMLElement => el !== null
    )
    if (targets.length === 0) return

    const visibility = new Map<string, number>()
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          visibility.set(entry.target.id, entry.intersectionRatio)
        }
        let best: { id: string; ratio: number } | null = null
        for (const [id, ratio] of visibility) {
          if (ratio <= 0) continue
          if (!best || ratio > best.ratio) best = { id, ratio }
        }
        if (!best) return
        const next = `#${best.id}`
        setActive((prev) => (prev === next ? prev : next))
      },
      { rootMargin: '-80px 0px -55% 0px', threshold: [0, 0.25, 0.5, 0.75, 1] }
    )
    targets.forEach((el) => {
      observer.observe(el)
    })
    return () => {
      observer.disconnect()
    }
  }, [])

  return active
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

  const playgroundFilteredModels = usePlaygroundFilteredModels({
    credentialId,
    includeRoutes: true,
  })
  const {
    credentialById,
    credentialsLoading,
    candidateModels: guideModelCandidates,
    routes: guideRoutes,
    ensureModelNameLoaded,
    isRefreshing: playgroundModelsRefreshing,
    refreshAll: refreshPlaygroundModels,
  } = playgroundFilteredModels

  const workspaceTeamId = useGatewayWorkspaceTeamId()
  const membershipTeamIds = useGatewayMembershipTeamIds()
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
  const { plain: revealedKey, isRevealing } = virtualKey
  const [gatewayV1Base] = useState(resolveGatewayV1BaseUrl)
  const [activeModel, setActiveModel] = useState<string>(PLACEHOLDER_MODEL)
  const [playgroundMode, setPlaygroundMode] = useState<PlaygroundMode>('chat')
  const [apiFlavor, setApiFlavor] = useState<ApiFlavor>('openai')
  const [exampleStream, setExampleStream] = useState(true)
  const [responseTab, setResponseTab] = useState<ResponseTab>('openai-sse')

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
    () => buildGuideSnippets(gatewayV1Base, displayKey, activeModel || PLACEHOLDER_MODEL),
    [gatewayV1Base, displayKey, activeModel]
  )
  const clientIntegrations = useMemo(
    () =>
      buildClientIntegrations(
        gatewayV1Base,
        displayKey,
        activeModel || PLACEHOLDER_MODEL,
        snippets
      ),
    [gatewayV1Base, displayKey, activeModel, snippets]
  )

  useEffect(() => {
    if (location.hash !== '#clients' && !keyIdFromQuery) return
    const frame = requestAnimationFrame(() => {
      scrollToGuideSection('#clients')
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

  const activeAnchor = useActiveGuideAnchor()
  const quickSteps = useMemo(() => buildQuickSteps(workspaceTeamId), [workspaceTeamId])
  const troubleshooting = useMemo(() => buildTroubleshooting(workspaceTeamId), [workspaceTeamId])

  return (
    <div className="w-full">
      <header className="py-6">
        <h2 className="text-balance text-2xl font-semibold tracking-tight">调用指南</h2>
      </header>

      <GuideAnchorNav active={activeAnchor} />

      <div className="mt-4 space-y-4">
        <section aria-labelledby="quick-start-heading" className="scroll-mt-20">
          <h3 id="quick-start-heading" className="sr-only">
            快速上手
          </h3>
          <div className="grid gap-3 rounded-xl border border-border/60 bg-background p-3 shadow-sm md:grid-cols-3">
            {quickSteps.map((item) => (
              <QuickStepItem key={item.step} item={item} />
            ))}
          </div>
        </section>

        <section id="playground" aria-labelledby="playground-heading" className="scroll-mt-20">
          <h3 id="playground-heading" className="sr-only">
            在线试调
          </h3>
          <div className="mb-2 flex justify-end">
            <GatewayRefreshButton
              isFetching={combineFetching(playgroundModelsRefreshing, virtualKey.isRefreshingKeys)}
              ariaLabel="刷新试调数据"
              onRefresh={handlePlaygroundRefresh}
            />
          </div>
          <Suspense fallback={<GuideSectionFallback />}>
            <PlaygroundCard
              baseUrl={gatewayV1Base}
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

        <section id="clients" aria-labelledby="clients-heading" className="scroll-mt-20">
          <h3 id="clients-heading" className="sr-only">
            第三方客户端集成
          </h3>
          <Suspense fallback={<GuideSectionFallback />}>
            <GuideClientIntegrationsSection
              clients={clientIntegrations}
              copiedKey={copiedKey}
              onCopy={handleCopy}
              keyHint={clientIntegrationsKeyHint}
            />
          </Suspense>
        </section>

        <section
          id="examples"
          aria-labelledby="examples-heading"
          className="scroll-mt-20 space-y-3"
        >
          <Card className={GUIDE_CARD_CLASS}>
            <CardHeader className="pb-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="space-y-1">
                  <CardTitle id="examples-heading" className="text-base">
                    代码示例
                  </CardTitle>
                  <div className="flex flex-wrap items-center gap-1.5 text-sm text-muted-foreground">
                    <span>当前试调：</span>
                    <Badge variant="secondary" className="font-normal">
                      {PLAYGROUND_MODE_LABELS[playgroundMode]}
                    </Badge>
                  </div>
                </div>
                {playgroundMode === 'chat' ? (
                  <div className="flex items-center gap-2 rounded-md border bg-muted/40 px-3 py-1.5">
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
            <CardContent className="pt-5">
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

                  <TabsContent value="openai" className="space-y-3">
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

                  <TabsContent value="anthropic" className="space-y-3">
                    <EndpointBadge
                      endpoint={snippets.anthropic.endpoint}
                      mode={exampleStream ? 'stream' : 'json'}
                      copyKey="anthropicEndpoint"
                      copied={copiedKey === 'anthropicEndpoint'}
                      onCopy={handleCopy}
                    />
                    <FlavorExamples
                      curl={exampleStream ? snippets.anthropic.curlStream : snippets.anthropic.curl}
                      ts={exampleStream ? snippets.anthropic.tsStream : snippets.anthropic.ts}
                      py={exampleStream ? snippets.anthropic.pyStream : snippets.anthropic.py}
                      keyPrefix={`anthropic-${exampleStream ? 'stream' : 'json'}`}
                      copiedKey={copiedKey}
                      onCopy={handleCopy}
                    />
                  </TabsContent>
                </Tabs>
              ) : mediaModeSnippets ? (
                <div className="space-y-3">
                  {mediaModeSnippets.hint ? (
                    <p className="text-sm text-muted-foreground">
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
        </section>

        <section
          id="reference"
          aria-labelledby="reference-heading"
          className="scroll-mt-20 space-y-3"
        >
          <Card className={GUIDE_CARD_CLASS}>
            <CardHeader className="pb-4">
              <CardTitle id="reference-heading" className="text-base">
                能力与返回参考
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 pt-5">
              <GuideReferenceSection title="按能力查看示例" defaultOpen>
                <p className="mb-3 text-sm text-muted-foreground">
                  图片生成、视频生成的 curl 示例见上方
                  <a
                    href="#examples"
                    className="mx-1 text-primary underline-offset-4 hover:underline"
                    onClick={(event) => {
                      event.preventDefault()
                      scrollToGuideSection('#examples')
                    }}
                  >
                    代码示例
                  </a>
                  （随在线试调 Tab 切换）。
                </p>
                <div id="capabilities" className="scroll-mt-20 space-y-3">
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
        </section>

        <section
          id="troubleshooting"
          aria-labelledby="troubleshooting-heading"
          className="scroll-mt-20"
        >
          <Card className={GUIDE_CARD_CLASS}>
            <CardHeader className="pb-4">
              <CardTitle id="troubleshooting-heading" className="text-base">
                异常排查
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-5">
              <div className="grid gap-3 md:grid-cols-2">
                {troubleshooting.map((item) => (
                  <TroubleshootingCard key={item.code} item={item} />
                ))}
              </div>
            </CardContent>
          </Card>
        </section>
      </div>
    </div>
  )
}

function scrollToGuideSection(href: string): void {
  const target = document.getElementById(href.slice(1))
  if (!target) return
  target.scrollIntoView({ behavior: 'smooth', block: 'start' })
  window.history.replaceState(null, '', href)
}

const GuideNavTab = memo(function GuideNavTab({
  href,
  label,
  isActive,
}: Readonly<{
  href: string
  label: string
  isActive: boolean
}>): React.JSX.Element {
  return (
    <a
      href={href}
      role="tab"
      aria-selected={isActive}
      aria-current={isActive ? 'true' : undefined}
      onClick={(event) => {
        event.preventDefault()
        scrollToGuideSection(href)
      }}
      className={cn(
        'shrink-0 rounded-md px-3 py-1.5 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        isActive
          ? 'bg-muted font-medium text-foreground shadow-sm'
          : 'text-muted-foreground hover:bg-muted/60 hover:text-foreground'
      )}
    >
      {label}
    </a>
  )
})

const GuideAnchorNav = memo(function GuideAnchorNav({
  active,
}: Readonly<{ active: string }>): React.JSX.Element {
  return (
    <nav
      aria-label="调用指南目录"
      className="sticky top-0 z-30 -mx-6 border-b border-border/60 bg-background px-6 py-1.5 shadow-sm"
    >
      <div
        role="tablist"
        aria-orientation="horizontal"
        className="-mx-1 flex items-center gap-0.5 overflow-x-auto px-1 text-sm"
      >
        {GUIDE_NAV_ITEMS.map(([href, label]) => (
          <GuideNavTab key={href} href={href} label={label} isActive={href === active} />
        ))}
      </div>
    </nav>
  )
})

function QuickStepItem({ item }: Readonly<{ item: QuickStep }>): React.JSX.Element {
  const content = (
    <div className="flex min-w-0 items-start gap-3 rounded-lg px-3 py-2 hover:bg-muted/50">
      <Badge
        variant="secondary"
        className="mt-0.5 h-6 w-6 shrink-0 justify-center rounded-full p-0"
      >
        {item.step}
      </Badge>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium">{item.title}</p>
      </div>
      {item.href.startsWith('#') ? null : (
        <ExternalLink
          className="mt-1 h-3.5 w-3.5 shrink-0 text-muted-foreground"
          aria-hidden="true"
        />
      )}
    </div>
  )

  if (item.href.startsWith('#')) {
    return (
      <a
        href={item.href}
        className="rounded-lg underline-offset-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
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
    <Collapsible defaultOpen={defaultOpen} className="rounded-lg border">
      <CollapsibleTrigger className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm font-medium hover:bg-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring [&[data-state=open]>svg]:rotate-180">
        {title}
        <ChevronDown
          className="h-4 w-4 shrink-0 text-muted-foreground transition-transform"
          aria-hidden="true"
        />
      </CollapsibleTrigger>
      <CollapsibleContent className="border-t p-3">{children}</CollapsibleContent>
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
    <div className="rounded-lg border p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-sm font-medium">
            <Badge variant="outline" className="mr-2 font-mono" translate="no">
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
          className="shrink-0 text-sm text-primary underline-offset-4 hover:underline"
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
    <Collapsible defaultOpen={module.id === 'tools'} className="rounded-md border">
      <CollapsibleTrigger className="flex w-full items-start justify-between gap-3 px-3 py-2 text-left hover:bg-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring [&[data-state=open]>svg]:rotate-180">
        <p className="min-w-0 text-sm font-medium">{module.title}</p>
        <ChevronDown
          className="mt-1 h-4 w-4 shrink-0 text-muted-foreground transition-transform"
          aria-hidden="true"
        />
      </CollapsibleTrigger>
      <CollapsibleContent className="space-y-3 border-t p-3">
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
    <div className="flex items-center gap-2 rounded-md border bg-muted/30 px-3 py-2 text-xs">
      <Badge variant="secondary" className="shrink-0 font-mono">
        {method}
      </Badge>
      <span className="min-w-0 flex-1 truncate font-mono text-foreground/90" translate="no">
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
      <TabsList className="h-8">
        <TabsTrigger value="curl" className="h-6 px-3 text-xs">
          curl
        </TabsTrigger>
        <TabsTrigger value="ts" className="h-6 px-3 text-xs">
          TypeScript
        </TabsTrigger>
        <TabsTrigger value="py" className="h-6 px-3 text-xs">
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
      <pre className="overflow-x-auto rounded-md border bg-muted/50 p-4 pr-24 text-xs leading-relaxed">
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
