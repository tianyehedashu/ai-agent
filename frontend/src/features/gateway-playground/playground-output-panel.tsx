import { memo, useMemo } from 'react'

import type { MyPriceRow } from '@/api/gateway'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { estimateUsageCostDisplay } from '@/features/gateway-pricing/estimate-usage-cost'
import { usePricingEstimate } from '@/features/gateway-pricing/use-pricing-estimate'
import { useCopyToClipboard } from '@/hooks/use-copy-to-clipboard'
import { AlertCircle, Check, Copy, Loader2 } from '@/lib/lucide-icons'
import { formatMoney } from '@/lib/money'
import { cn } from '@/lib/utils'
import type { DisplayCurrency } from '@/types/money'

import { ImageGenOutput } from './modes/image-gen-output'
import { VideoOutput } from './modes/video-output'
import { isImageGenRaw, isVideoGenRaw, safeStringify } from './playground-raw-response'

import type { PlaygroundMode } from './playground-mode-filter'
import type {
  PlaygroundApiFlavor,
  PlaygroundError,
  PlaygroundMetadata,
  PlaygroundRawResponse,
  PlaygroundRequestSnapshot,
  PlaygroundStatus,
} from './types'

export const PlaygroundOutputPanel = memo(function PlaygroundOutputPanel({
  status,
  content,
  thinkingContent,
  metadata,
  error,
  rawResponse,
  lastRequest,
  priceRow,
  currency,
  flavor,
  stream,
  endpoint,
  playgroundMode,
}: Readonly<{
  status: PlaygroundStatus
  content: string
  thinkingContent?: string
  metadata: PlaygroundMetadata | null
  error: PlaygroundError | null
  rawResponse: PlaygroundRawResponse
  lastRequest: PlaygroundRequestSnapshot | null
  priceRow?: MyPriceRow
  currency: DisplayCurrency
  flavor: PlaygroundApiFlavor
  stream: boolean
  endpoint: string
  playgroundMode: PlaygroundMode
}>): React.JSX.Element | null {
  const responseJson = useMemo(() => (rawResponse ? safeStringify(rawResponse) : ''), [rawResponse])
  const requestJson = useMemo(() => (lastRequest ? safeStringify(lastRequest) : ''), [lastRequest])
  const thinking = thinkingContent ?? ''
  const hasResponseBody =
    content.length > 0 || thinking.length > 0 || rawResponse !== null || lastRequest !== null

  if (status === 'idle' && !content && !error) {
    return null
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
        playgroundMode={playgroundMode}
      />
      {error ? <ErrorBlock error={error} requestId={metadata?.requestId} /> : null}
      {hasResponseBody ? (
        <Tabs defaultValue="text" className="w-full">
          <TabsList className="h-8">
            <TabsTrigger value="text" className="h-6 px-3 text-xs">
              文本
            </TabsTrigger>
            {lastRequest ? (
              <TabsTrigger value="request" className="h-6 px-3 text-xs">
                请求
              </TabsTrigger>
            ) : null}
            <TabsTrigger value="response" className="h-6 px-3 text-xs">
              响应
            </TabsTrigger>
          </TabsList>
          <TabsContent value="text" className="space-y-3">
            {isImageGenRaw(rawResponse) ? <ImageGenOutput items={rawResponse.items} /> : null}
            {isVideoGenRaw(rawResponse) ? <VideoOutput url={rawResponse.url} /> : null}
            {thinking.length > 0 ? (
              <div className="space-y-1.5">
                <p className="text-xs font-medium text-muted-foreground">思考过程</p>
                <pre className="max-h-40 overflow-auto whitespace-pre-wrap break-words rounded-md border border-purple-500/20 bg-purple-500/5 p-3 text-sm leading-relaxed">
                  <code>{thinking}</code>
                </pre>
              </div>
            ) : null}
            <div className="space-y-1.5">
              {thinking.length > 0 ? (
                <p className="text-xs font-medium text-muted-foreground">回复</p>
              ) : null}
              <pre
                className={cn(
                  'max-h-72 overflow-auto whitespace-pre-wrap break-words rounded-md border bg-background p-4 text-sm leading-relaxed',
                  !content && 'text-muted-foreground'
                )}
              >
                <code>
                  {content ||
                    (thinking.length > 0
                      ? '（暂无正文，仅返回思考内容）'
                      : '（无文本，仅工具调用或空响应）')}
                  {showStreamCursor ? (
                    <span
                      className="ml-0.5 inline-block h-3.5 w-1.5 translate-y-0.5 animate-pulse rounded-sm bg-amber-500 align-middle"
                      aria-hidden="true"
                    />
                  ) : null}
                </code>
              </pre>
            </div>
          </TabsContent>
          {lastRequest ? (
            <TabsContent value="request">
              <PlaygroundJsonBlock code={requestJson} copyLabel="复制请求" />
            </TabsContent>
          ) : null}
          <TabsContent value="response">
            <PlaygroundJsonBlock code={responseJson} copyLabel="复制响应" />
          </TabsContent>
        </Tabs>
      ) : null}
      {metadata ? (
        <PlaygroundMetadataFooter metadata={metadata} priceRow={priceRow} currency={currency} />
      ) : null}
    </div>
  )
})

const PlaygroundJsonBlock = memo(function PlaygroundJsonBlock({
  code,
  copyLabel,
}: Readonly<{
  code: string
  copyLabel: string
}>): React.JSX.Element {
  const [copy, copied] = useCopyToClipboard()

  return (
    <div className="relative">
      <div className="absolute right-2 top-2 z-10">
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="h-8 w-8 shrink-0 bg-background/80 backdrop-blur-sm"
          aria-label={copyLabel}
          disabled={!code}
          onClick={() => {
            if (!code) return
            void copy(code)
          }}
        >
          {copied ? (
            <Check className="h-4 w-4" aria-hidden="true" />
          ) : (
            <Copy className="h-4 w-4" aria-hidden="true" />
          )}
        </Button>
      </div>
      <pre className="max-h-[min(32rem,65vh)] min-h-80 overflow-auto rounded-md border bg-background p-4 pr-14 text-sm leading-relaxed">
        <code translate="no">{code || '（暂无内容）'}</code>
      </pre>
    </div>
  )
})

function PlaygroundMetadataFooter({
  metadata,
  priceRow,
  currency,
}: Readonly<{
  metadata: PlaygroundMetadata
  priceRow?: MyPriceRow
  currency: DisplayCurrency
}>): React.JSX.Element {
  const responseCostLabel =
    metadata.responseCostUsd !== undefined
      ? formatMoney(metadata.responseCostUsd, { currency: 'USD', precision: 4 })
      : null
  const needEstimate = responseCostLabel === null
  const apiEstimate = usePricingEstimate({
    gatewayModelId: priceRow?.gateway_model_id,
    inputTokens: metadata.promptTokens,
    completionTokens: metadata.completionTokens,
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
  return (
    <MetadataRow
      metadata={metadata}
      responseCostLabel={responseCostLabel}
      estimatedCost={estimatedCost}
    />
  )
}

function ResponseModeHeader({
  flavor,
  stream,
  endpoint,
  streaming,
  playgroundMode,
}: Readonly<{
  flavor: PlaygroundApiFlavor
  stream: boolean
  endpoint: string
  streaming: boolean
  playgroundMode: PlaygroundMode
}>): React.JSX.Element {
  const modeBadge =
    playgroundMode === 'image_gen'
      ? '图片生成'
      : playgroundMode === 'video_gen'
        ? '视频生成'
        : playgroundMode === 'vision'
          ? '视觉理解'
          : flavor === 'anthropic'
            ? 'Anthropic · Messages'
            : 'OpenAI · Chat'
  return (
    <div className="flex flex-wrap items-center gap-1.5 text-xs">
      <Badge variant="secondary" className="font-mono">
        {modeBadge}
      </Badge>
      {stream ? (
        <Badge variant="outline" className="gap-1 border-amber-500/40 font-mono text-amber-600">
          {streaming ? <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" /> : null}
          SSE
        </Badge>
      ) : (
        <Badge variant="outline" className="gap-1 font-mono">
          JSON
        </Badge>
      )}
      <span className="ml-1 truncate font-mono text-muted-foreground" translate="no">
        {endpoint}
      </span>
    </div>
  )
}

function ErrorBlock({
  error,
  requestId,
}: Readonly<{ error: PlaygroundError; requestId?: string }>): React.JSX.Element {
  return (
    <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
      <div className="mb-1 flex items-center gap-2 font-medium">
        <AlertCircle className="h-4 w-4" aria-hidden="true" />
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
      <p className="whitespace-pre-wrap break-words font-medium">{error.message}</p>
      {error.hint ? (
        <p className="mt-1 whitespace-pre-wrap break-words text-xs">{error.hint}</p>
      ) : null}
      {requestId ? (
        <p className="mt-1 font-mono text-xs text-destructive/90" translate="no">
          request_id: {requestId}
        </p>
      ) : null}
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
