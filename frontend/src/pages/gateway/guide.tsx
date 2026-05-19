/**
 * AI Gateway · 调用指南
 *
 * - 在线试调（PlaygroundCard）
 * - 调用配置：Base URL / 鉴权 / model / 流式字段
 * - 示例代码：OpenAI 兼容（/v1/chat/completions） + Anthropic 兼容（/v1/messages）
 *   每个风格内支持 curl / TS / Python，流式 toggle 同步切换示例代码与典型返回默认 Tab
 * - 典型返回：4 个 Tab 横向对比（OpenAI/Anthropic × 非流式/流式），用 Badge 突出 content-type
 */

import { useCallback, useEffect, useMemo, useState } from 'react'
import type React from 'react'

import { Link } from 'react-router-dom'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { PlaygroundCard } from '@/features/gateway-playground/playground-card'
import { useCopyToClipboardKeyed } from '@/hooks/use-copy-to-clipboard'
import { resolveGatewayV1BaseUrl } from '@/lib/gateway-v1-base-url'
import {
  Check,
  Copy,
  ExternalLink,
  FileText,
  ChevronDown,
  Sparkles,
  Terminal,
  Zap,
} from '@/lib/lucide-icons'
import { cn } from '@/lib/utils'
import {
  buildCapabilityModules,
  type CapabilityGuideModule,
  type FlavorCodeTriple,
} from '@/pages/gateway/guide-capability-snippets'
import { buildGuideSnippets, type GuideSnippets } from '@/pages/gateway/guide-snippets'

const PLACEHOLDER_KEY = 'sk-gw-your-virtual-key'
const PLACEHOLDER_MODEL = 'your-model-or-route-alias'

type ApiFlavor = 'openai' | 'anthropic'
type ResponseTab = 'openai-json' | 'openai-sse' | 'anthropic-json' | 'anthropic-sse'

const QUICK_STEPS = [
  {
    step: 1,
    title: '创建虚拟 Key',
    description: '明文仅显示一次，请妥善保存。',
    href: '/gateway/keys',
    linkLabel: '前往虚拟 Key',
  },
  {
    step: 2,
    title: '选择模型或路由',
    description: 'model 填模型别名或虚拟路由名。',
    href: '/gateway/models',
    linkLabel: '查看模型',
  },
  {
    step: 3,
    title: '复制示例并调用',
    description: '把 Base URL 与 Key 填入 SDK 或 curl。',
    href: '#examples',
    linkLabel: '查看示例',
  },
] as const

const TROUBLESHOOTING = [
  {
    code: '401',
    title: '鉴权失败',
    hint: '检查 Header、Key 明文和撤销状态。',
    href: '/gateway/keys',
    linkLabel: '虚拟 Key',
  },
  {
    code: '404',
    title: '模型不存在',
    hint: 'model 需匹配模型别名或路由名。',
    href: '/gateway/models',
    linkLabel: '模型',
  },
  {
    code: '429',
    title: '限流',
    hint: '检查 RPM/TPM、套餐或预算。',
    href: '/gateway/budgets',
    linkLabel: '预算配额',
  },
  {
    code: '5xx',
    title: '上游失败',
    hint: '到调用日志查看 request_id 与上游错误。',
    href: '/gateway/logs',
    linkLabel: '调用日志',
  },
] as const

const GUIDE_NAV_ITEMS = [
  ['#playground', '在线试调'],
  ['#config', '接入配置'],
  ['#examples', '代码示例'],
  ['#reference', '能力参考'],
  ['#troubleshooting', '异常排查'],
] as const

const ANTHROPIC_NATIVE_FIELDS = [
  'thinking',
  'cache_control',
  'tool_result',
  'image',
  'top_k',
] as const

type QuickStep = (typeof QUICK_STEPS)[number]
type TroubleshootingItem = (typeof TROUBLESHOOTING)[number]

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
  const [gatewayV1Base] = useState(resolveGatewayV1BaseUrl)
  const [activeModel, setActiveModel] = useState<string>(PLACEHOLDER_MODEL)
  const [apiFlavor, setApiFlavor] = useState<ApiFlavor>('openai')
  const [exampleStream, setExampleStream] = useState(true)
  const [responseTab, setResponseTab] = useState<ResponseTab>('openai-sse')

  const snippets = useMemo(
    () => buildGuideSnippets(gatewayV1Base, PLACEHOLDER_KEY, activeModel || PLACEHOLDER_MODEL),
    [gatewayV1Base, activeModel]
  )
  const capabilityModules = useMemo(
    () => buildCapabilityModules(gatewayV1Base, PLACEHOLDER_KEY, activeModel || PLACEHOLDER_MODEL),
    [gatewayV1Base, activeModel]
  )
  const [copy, copiedKey] = useCopyToClipboardKeyed<string>()
  const handleCopy = useCallback(
    (key: string, text: string) => {
      void copy(text, key)
    },
    [copy]
  )
  const handlePlaygroundModelChange = useCallback((next: string) => {
    setActiveModel(next || PLACEHOLDER_MODEL)
  }, [])

  // 示例流式 / API 风格变化时，把典型返回 Tab 默认联动到对应组合，但仍允许独立切换
  useEffect(() => {
    setResponseTab(`${apiFlavor}-${exampleStream ? 'sse' : 'json'}` as ResponseTab)
  }, [apiFlavor, exampleStream])

  const activeAnchor = useActiveGuideAnchor()

  return (
    <div className="space-y-5">
      <header className="space-y-1">
        <h2 className="text-balance text-2xl font-semibold tracking-tight">调用指南</h2>
        <p className="max-w-2xl text-sm text-muted-foreground">
          先在控制台完成一次试调，再复制生产接入所需的 Base URL、鉴权 Header 和示例代码。
        </p>
      </header>

      <GuideAnchorNav active={activeAnchor} />

      <section aria-labelledby="quick-start-heading" className="scroll-mt-20">
        <h3 id="quick-start-heading" className="sr-only">
          快速上手
        </h3>
        <div className="grid gap-2 rounded-xl border bg-background p-2 md:grid-cols-3">
          {QUICK_STEPS.map((item) => (
            <QuickStepItem key={item.step} item={item} />
          ))}
        </div>
      </section>

      <section id="playground" aria-labelledby="playground-heading" className="scroll-mt-20">
        <h3 id="playground-heading" className="sr-only">
          在线试调
        </h3>
        <PlaygroundCard baseUrl={gatewayV1Base} onModelChange={handlePlaygroundModelChange} />
      </section>

      <section id="config" aria-labelledby="config-heading" className="scroll-mt-20">
        <Card>
          <CardHeader>
            <CardTitle id="config-heading" className="text-base">
              接入配置
            </CardTitle>
            <CardDescription>
              生产凭证建议仅保存在服务端。域名默认跟随站点，也可通过 VITE_API_URL 配置。
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 lg:grid-cols-3">
              <ConfigRow
                label="Base URL"
                value={snippets.baseUrl}
                mono
                copyKey="baseUrl"
                copied={copiedKey === 'baseUrl'}
                onCopy={handleCopy}
              />
              <ConfigRow
                label="鉴权 Header"
                value={
                  apiFlavor === 'openai'
                    ? snippets.openai.authHeader
                    : snippets.anthropic.authHeader
                }
                mono
                copyKey={`${apiFlavor}AuthHeader`}
                copied={copiedKey === `${apiFlavor}AuthHeader`}
                onCopy={handleCopy}
              />
              <ConfigRow
                label="model"
                value={activeModel}
                mono
                hint={
                  activeModel === PLACEHOLDER_MODEL
                    ? '从上方试调选择模型后会同步。'
                    : '已从试调区同步。'
                }
              />
            </div>
            <Collapsible>
              <CollapsibleTrigger className="flex w-full items-center justify-between rounded-md border px-3 py-2 text-left text-sm font-medium hover:bg-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring [&[data-state=open]>svg]:rotate-180">
                更多配置与 Anthropic 原生字段
                <ChevronDown
                  className="h-4 w-4 text-muted-foreground transition-transform"
                  aria-hidden="true"
                />
              </CollapsibleTrigger>
              <CollapsibleContent className="space-y-4 pt-4">
                <div className="grid gap-3 lg:grid-cols-2">
                  <ConfigRow
                    label="Anthropic SDK baseURL"
                    value={snippets.anthropicBaseUrl}
                    mono
                    hint="Anthropic 官方 SDK 的 baseURL，末尾不含 /v1。"
                    copyKey="anthropicBaseUrl"
                    copied={copiedKey === 'anthropicBaseUrl'}
                    onCopy={handleCopy}
                  />
                  <ConfigRow
                    label="流式 stream"
                    value="true"
                    mono
                    hint="在 JSON body 设置 stream: true，响应为 SSE。"
                    copyKey="streamHint"
                    copyText={snippets.streamHint}
                    copied={copiedKey === 'streamHint'}
                    onCopy={handleCopy}
                  />
                </div>
                <div className="flex flex-wrap gap-2">
                  <Badge variant="secondary">Anthropic 原生通道</Badge>
                  {ANTHROPIC_NATIVE_FIELDS.map((name) => (
                    <Badge key={name} variant="outline" className="font-mono text-xs">
                      {name}
                    </Badge>
                  ))}
                </div>
              </CollapsibleContent>
            </Collapsible>
          </CardContent>
        </Card>
      </section>

      <section id="examples" aria-labelledby="examples-heading" className="scroll-mt-20 space-y-3">
        <Card>
          <CardHeader className="pb-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="space-y-1">
                <CardTitle id="examples-heading" className="text-base">
                  代码示例
                </CardTitle>
                <CardDescription>
                  切换 API 风格、流式模式和语言；下方返回示例会同步。
                </CardDescription>
              </div>
              <div className="flex items-center gap-2 rounded-md border bg-muted/40 px-3 py-1.5">
                <Zap
                  className={cn(
                    'h-4 w-4',
                    exampleStream ? 'text-amber-500' : 'text-muted-foreground'
                  )}
                  aria-hidden="true"
                />
                <Label htmlFor="example-stream" className="cursor-pointer text-sm">
                  流式 SSE
                </Label>
                <Switch
                  id="example-stream"
                  checked={exampleStream}
                  onCheckedChange={setExampleStream}
                />
              </div>
            </div>
          </CardHeader>
          <CardContent>
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
                  authHeader={snippets.openai.authHeader}
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
                  authHeader={snippets.anthropic.authHeader}
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
          </CardContent>
        </Card>
      </section>

      <section
        id="reference"
        aria-labelledby="reference-heading"
        className="scroll-mt-20 space-y-3"
      >
        <Card>
          <CardHeader>
            <CardTitle id="reference-heading" className="text-base">
              能力与返回参考
            </CardTitle>
            <CardDescription>
              生产接入时再展开查看。能力示例跟随上方 API 风格，返回示例跟随流式设置。
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <GuideReferenceSection title="按能力查看示例" defaultOpen>
              <div id="capabilities" className="scroll-mt-20 space-y-3">
                {capabilityModules.map((mod) => (
                  <CapabilityGuideCard
                    key={mod.id}
                    module={mod}
                    apiFlavor={apiFlavor}
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
              <p className="mb-3 text-sm text-muted-foreground">
                使用{' '}
                <span className="font-mono" translate="no">
                  GET /v1/models
                </span>{' '}
                查看当前 Key 可见模型；也可在
                <Link
                  to="/gateway/models"
                  className="text-primary underline-offset-4 hover:underline"
                >
                  模型
                </Link>
                、
                <Link
                  to="/gateway/routes"
                  className="text-primary underline-offset-4 hover:underline"
                >
                  虚拟路由
                </Link>
                页面确认名称。
              </p>
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
        <Card>
          <CardHeader>
            <CardTitle id="troubleshooting-heading" className="text-base">
              异常排查
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-3 md:grid-cols-2">
              {TROUBLESHOOTING.map((item) => (
                <TroubleshootingCard key={item.code} item={item} />
              ))}
            </div>
          </CardContent>
        </Card>
      </section>
    </div>
  )
}

function GuideAnchorNav({ active }: Readonly<{ active: string }>): React.JSX.Element {
  const handleClick = useCallback((event: React.MouseEvent<HTMLAnchorElement>, href: string) => {
    const id = href.slice(1)
    const target = document.getElementById(id)
    if (!target) return
    event.preventDefault()
    target.scrollIntoView({ behavior: 'smooth', block: 'start' })
    window.history.replaceState(null, '', href)
  }, [])

  return (
    <nav
      aria-label="调用指南目录"
      className="sticky top-0 z-20 -mx-6 border-b border-border/60 bg-background/85 px-6 py-2 backdrop-blur supports-[backdrop-filter]:bg-background/70"
    >
      <div
        role="tablist"
        aria-orientation="horizontal"
        className="-mx-1 flex items-center gap-0.5 overflow-x-auto px-1 text-sm"
      >
        {GUIDE_NAV_ITEMS.map(([href, label]) => {
          const isActive = href === active
          return (
            <a
              key={href}
              href={href}
              role="tab"
              aria-selected={isActive}
              aria-current={isActive ? 'true' : undefined}
              onClick={(event) => {
                handleClick(event, href)
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
        })}
      </div>
    </nav>
  )
}

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
        <p className="text-xs text-muted-foreground">{item.description}</p>
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
          title="POST /v1/chat/completions"
          contentType="application/json"
          mode="json"
          code={snippets.openai.responseJson}
          copyKey="openaiResponseJson"
          copied={copiedKey === 'openaiResponseJson'}
          onCopy={onCopy}
        />
      </TabsContent>
      <TabsContent value="openai-sse">
        <ResponseExample
          title="POST /v1/chat/completions（stream: true）"
          contentType="text/event-stream"
          mode="sse"
          code={snippets.openai.responseSse}
          copyKey="openaiResponseSse"
          copied={copiedKey === 'openaiResponseSse'}
          onCopy={onCopy}
        />
      </TabsContent>
      <TabsContent value="anthropic-json">
        <ResponseExample
          title="POST /v1/messages"
          contentType="application/json"
          mode="json"
          code={snippets.anthropic.responseJson}
          copyKey="anthropicResponseJson"
          copied={copiedKey === 'anthropicResponseJson'}
          onCopy={onCopy}
        />
      </TabsContent>
      <TabsContent value="anthropic-sse">
        <ResponseExample
          title="POST /v1/messages（stream: true）"
          contentType="text/event-stream"
          mode="sse"
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
  return (
    <div className="rounded-lg border p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-medium">
            <Badge variant="outline" className="mr-2 font-mono" translate="no">
              {item.code}
            </Badge>
            {item.title}
          </p>
          <p className="mt-1 text-sm text-muted-foreground">{item.hint}</p>
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
  copiedKey,
  onCopy,
}: Readonly<{
  module: CapabilityGuideModule
  apiFlavor: ApiFlavor
  copiedKey: string | null
  onCopy: (key: string, text: string) => void
}>): React.JSX.Element {
  const snippets: FlavorCodeTriple = apiFlavor === 'openai' ? module.openai : module.anthropic
  const keyPrefix = `cap-${module.id}-${apiFlavor}`

  return (
    <Collapsible defaultOpen={module.id === 'tools'} className="rounded-md border">
      <CollapsibleTrigger className="flex w-full items-start justify-between gap-3 px-3 py-2 text-left hover:bg-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring [&[data-state=open]>svg]:rotate-180">
        <div className="min-w-0 space-y-0.5">
          <p className="text-sm font-medium">{module.title}</p>
          <p className="text-xs text-muted-foreground">{module.description}</p>
        </div>
        <ChevronDown
          className="mt-1 h-4 w-4 shrink-0 text-muted-foreground transition-transform"
          aria-hidden="true"
        />
      </CollapsibleTrigger>
      <CollapsibleContent className="border-t p-3">
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

function ConfigRow({
  label,
  value,
  hint,
  mono,
  copyKey,
  copyText,
  copied,
  onCopy,
}: Readonly<{
  label: string
  value: string
  hint?: string
  mono?: boolean
  copyKey?: string
  copyText?: string
  copied?: boolean
  onCopy?: (key: string, text: string) => void
}>): React.JSX.Element {
  const textToCopy = copyText ?? value
  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0 flex-1">
        <p className="text-xs font-medium text-muted-foreground">{label}</p>
        <p
          className={cn('mt-0.5 break-all text-sm', mono && 'font-mono')}
          translate={mono ? 'no' : undefined}
        >
          {value}
        </p>
        {hint ? <p className="mt-1 text-xs text-muted-foreground">{hint}</p> : null}
      </div>
      {copyKey && onCopy ? (
        <CopyButton
          copied={copied ?? false}
          label={`复制 ${label}`}
          onCopy={() => {
            onCopy(copyKey, textToCopy)
          }}
        />
      ) : null}
    </div>
  )
}

function EndpointBadge({
  endpoint,
  authHeader,
  mode,
  copyKey,
  copied,
  onCopy,
}: Readonly<{
  endpoint: string
  authHeader: string
  mode: 'json' | 'stream'
  copyKey: string
  copied: boolean
  onCopy: (key: string, text: string) => void
}>): React.JSX.Element {
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-md border bg-muted/30 px-3 py-2 text-xs">
      <Badge variant="secondary" className="font-mono">
        {endpoint.split(' ')[0]}
      </Badge>
      <span className="font-mono text-foreground/90" translate="no">
        {endpoint.split(' ').slice(1).join(' ')}
      </span>
      {mode === 'stream' ? (
        <Badge variant="outline" className="gap-1 border-amber-500/40 text-amber-600">
          <Zap className="h-3 w-3" aria-hidden="true" />
          流式 SSE
        </Badge>
      ) : (
        <Badge variant="outline" className="gap-1">
          <FileText className="h-3 w-3" aria-hidden="true" />
          非流式 JSON
        </Badge>
      )}
      <Separator orientation="vertical" className="h-4" />
      <span className="text-muted-foreground">鉴权</span>
      <span className="font-mono text-foreground/90" translate="no">
        {authHeader}
      </span>
      <button
        type="button"
        onClick={() => {
          onCopy(copyKey, endpoint)
        }}
        className="ml-auto inline-flex items-center gap-1 text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
        aria-label="复制端点"
      >
        {copied ? (
          <Check className="h-3 w-3" aria-hidden="true" />
        ) : (
          <Copy className="h-3 w-3" aria-hidden="true" />
        )}
        {copied ? '已复制' : '复制端点'}
      </button>
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
  title,
  contentType,
  mode,
  code,
  copyKey,
  copied,
  onCopy,
}: Readonly<{
  title: string
  contentType: string
  mode: 'json' | 'sse'
  code: string
  copyKey: string
  copied: boolean
  onCopy: (key: string, text: string) => void
}>): React.JSX.Element {
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        {mode === 'sse' ? (
          <Badge variant="outline" className="gap-1 border-amber-500/40 text-amber-600">
            <Zap className="h-3 w-3" aria-hidden="true" />
            流式 SSE
          </Badge>
        ) : (
          <Badge variant="outline" className="gap-1">
            <FileText className="h-3 w-3" aria-hidden="true" />
            非流式 JSON
          </Badge>
        )}
        <span className="font-mono text-foreground/90" translate="no">
          {title}
        </span>
        <Badge variant="secondary" className="font-mono">
          Content-Type: {contentType}
        </Badge>
        {mode === 'sse' ? (
          <Badge variant="secondary" className="gap-1">
            <Sparkles className="h-3 w-3" aria-hidden="true" />
            增量推送 / 多帧
          </Badge>
        ) : (
          <Badge variant="secondary">一次性返回</Badge>
        )}
      </div>
      <CodeExampleCard
        title={mode === 'sse' ? '响应（按帧解析）' : '响应'}
        icon={mode === 'sse' ? Zap : FileText}
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
  onCopy,
}: Readonly<{
  copied: boolean
  label: string
  onCopy: () => void
}>): React.JSX.Element {
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
