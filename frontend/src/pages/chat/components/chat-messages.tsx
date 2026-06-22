import { memo, useEffect, useRef } from 'react'

import { User, Bot, Terminal } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism'

import { ProcessPanel } from '@/components/chat/process-panel'
import { ToolCallCard } from '@/components/chat/tool-call-card'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { ScrollArea } from '@/components/ui/scroll-area'
import type { Message, ProcessEvent, ToolCall } from '@/types'

interface ChatMessagesProps {
  messages: Message[]
  streamingContent: string
  isLoading: boolean
  pendingToolCalls?: ToolCall[]
  processRuns?: Record<string, ProcessEvent[]>
  currentRunId?: string | null
  /** 当前会话 ID，供 ProcessPanel 内视频任务块跳转链接使用 */
  sessionId?: string
  onPromptSelect?: (prompt: string) => void
}

const EMPTY_PROMPTS = [
  { title: '排查一次调用失败', prompt: '帮我分析最近一次 AI Gateway 调用失败的可能原因。' },
  { title: '整理模型路由策略', prompt: '帮我设计一个兼顾成本、延迟和稳定性的模型路由策略。' },
  { title: '生成 Listing 素材', prompt: '帮我为一个新品 Listing 生成卖点、标题和图片创意方向。' },
]

export default function ChatMessages({
  messages,
  streamingContent,
  isLoading,
  pendingToolCalls = [],
  processRuns = {},
  currentRunId = null,
  sessionId,
  onPromptSelect,
}: Readonly<ChatMessagesProps>): React.JSX.Element {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingContent, processRuns])

  // Empty state - 仅保留简短欢迎，不展示未实现的任务卡片
  if (messages.length === 0 && !isLoading) {
    return (
      <div className="flex h-full flex-col items-center justify-center px-4 py-8">
        <div className="w-full max-w-2xl text-center">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl border border-primary/20 bg-primary/10 shadow-sm shadow-primary/10">
            <Bot className="h-7 w-7 text-primary" />
          </div>
          <h1 className="text-xl font-semibold tracking-tight text-foreground sm:text-2xl">
            今天从哪里开始？
          </h1>
          <p className="mt-1.5 text-sm text-muted-foreground">选择一个任务，或直接开始新的对话。</p>
          {onPromptSelect ? (
            <div className="mt-6 grid gap-2 sm:grid-cols-3">
              {EMPTY_PROMPTS.map((item) => (
                <button
                  key={item.title}
                  type="button"
                  className="rounded-lg border border-border/70 bg-card/70 px-3 py-3 text-left text-sm transition-colors hover:border-primary/30 hover:bg-accent/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  onClick={() => {
                    onPromptSelect(item.prompt)
                  }}
                >
                  <span className="font-medium text-foreground">{item.title}</span>
                </button>
              ))}
            </div>
          ) : null}
        </div>
      </div>
    )
  }

  const activeRunEvents =
    currentRunId && currentRunId in processRuns ? processRuns[currentRunId] : undefined
  const isActiveRunCompleted =
    activeRunEvents?.some((event) => event.kind === 'done' || event.kind === 'error') ?? false

  return (
    <ScrollArea className="h-full">
      <div className="mx-auto max-w-3xl space-y-6 px-4 py-6 sm:px-6 sm:py-8">
        {messages.map((message) => {
          const runId = message.metadata?.runId
          const runEvents =
            typeof runId === 'string' && runId.length > 0 ? processRuns[runId] : undefined
          return (
            <MessageBubble
              key={message.id}
              message={message}
              runEvents={runEvents}
              sessionId={sessionId}
            />
          )
        })}

        {/* Streaming content with live process panel */}
        {(currentRunId !== null || isLoading) && (
          <div className="group flex items-start gap-3 animate-in fade-in slide-in-from-bottom-2">
            <Avatar className="mt-0.5 h-8 w-8 shrink-0 border border-primary/20 shadow-sm">
              <AvatarFallback className="bg-primary/10">
                <Bot className="h-4 w-4 text-primary" />
              </AvatarFallback>
            </Avatar>
            <div className="min-w-0 flex-1">
              {streamingContent && (
                <div className="markdown-body prose prose-slate dark:prose-invert max-w-none text-[15px] leading-relaxed">
                  <ReactMarkdown
                    components={{
                      code({ className, children, ...props }): React.JSX.Element {
                        const match = /language-(\w+)/.exec(className ?? '')
                        const childrenStr = Array.isArray(children)
                          ? children
                              .map((c) => {
                                if (typeof c === 'string') return c
                                if (typeof c === 'number' || typeof c === 'boolean')
                                  return String(c)
                                return ''
                              })
                              .join('')
                          : typeof children === 'string'
                            ? children
                            : typeof children === 'number' || typeof children === 'boolean'
                              ? String(children)
                              : ''
                        return match ? (
                          <SyntaxHighlighter
                            style={vscDarkPlus as Record<string, React.CSSProperties>}
                            language={match[1]}
                            PreTag="div"
                          >
                            {childrenStr.replace(/\n$/, '')}
                          </SyntaxHighlighter>
                        ) : (
                          <code className={className} {...props}>
                            {childrenStr}
                          </code>
                        )
                      },
                    }}
                  >
                    {streamingContent}
                  </ReactMarkdown>
                </div>
              )}
              {currentRunId &&
                currentRunId in processRuns &&
                processRuns[currentRunId].length > 0 && (
                  <div className="mt-3">
                    <ProcessPanel events={processRuns[currentRunId]} sessionId={sessionId} />
                  </div>
                )}

              {!streamingContent && pendingToolCalls.length === 0 && !isActiveRunCompleted && (
                <div className="flex items-center gap-2 py-2 text-sm text-muted-foreground">
                  <span className="relative flex h-2 w-2">
                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-75"></span>
                    <span className="relative inline-flex h-2 w-2 rounded-full bg-primary"></span>
                  </span>
                  思考中...
                </div>
              )}
            </div>
          </div>
        )}

        {/* Pending Tool Calls */}
        {pendingToolCalls.length > 0 && (
          <div className="ml-11 space-y-3">
            {pendingToolCalls.map((tc) => (
              <ToolCallCard key={tc.id} toolCall={tc} isPending />
            ))}
          </div>
        )}

        <div ref={bottomRef} className="h-4" />
      </div>
    </ScrollArea>
  )
}

const MessageBubble = memo(function MessageBubble({
  message,
  runEvents,
  sessionId,
}: Readonly<{
  message: Message
  runEvents: ProcessEvent[] | undefined
  sessionId?: string
}>): React.JSX.Element {
  const isUser = message.role === 'user'
  const usage = getMessageUsage(message)

  if (isUser) {
    return (
      <div className="flex items-start justify-end gap-3 animate-in fade-in slide-in-from-bottom-2">
        <div className="max-w-[85%] sm:max-w-[75%]">
          <div className="rounded-2xl rounded-br-md border border-primary/15 bg-primary/10 px-4 py-3 text-foreground shadow-sm shadow-primary/5">
            <div className="text-[15px] leading-relaxed">
              <ReactMarkdown>{message.content}</ReactMarkdown>
            </div>
          </div>
        </div>
        <Avatar className="mt-0.5 h-8 w-8 shrink-0 border border-primary/15 shadow-sm">
          <AvatarFallback className="bg-primary/10 text-primary">
            <User className="h-4 w-4" />
          </AvatarFallback>
        </Avatar>
      </div>
    )
  }

  return (
    <div className="group flex items-start gap-3 animate-in fade-in slide-in-from-bottom-2">
      <Avatar className="mt-0.5 h-8 w-8 shrink-0 border border-primary/20 shadow-sm">
        <AvatarFallback className="bg-primary/10">
          <Bot className="h-4 w-4 text-primary" />
        </AvatarFallback>
      </Avatar>

      <div className="min-w-0 flex-1">
        <div className="markdown-body prose prose-slate dark:prose-invert max-w-none text-[15px] leading-relaxed">
          <ReactMarkdown
            components={{
              code({ className, children, ...props }): React.JSX.Element {
                const match = /language-(\w+)/.exec(className ?? '')
                const childrenStr = Array.isArray(children)
                  ? children
                      .map((c) => {
                        if (typeof c === 'string') return c
                        if (typeof c === 'number' || typeof c === 'boolean') return String(c)
                        return ''
                      })
                      .join('')
                  : typeof children === 'string'
                    ? children
                    : typeof children === 'number' || typeof children === 'boolean'
                      ? String(children)
                      : ''
                return match ? (
                  <SyntaxHighlighter
                    style={vscDarkPlus as Record<string, React.CSSProperties>}
                    language={match[1]}
                    PreTag="div"
                  >
                    {childrenStr.replace(/\n$/, '')}
                  </SyntaxHighlighter>
                ) : (
                  <code className={className} {...props}>
                    {childrenStr}
                  </code>
                )
              },
            }}
          >
            {message.content}
          </ReactMarkdown>
        </div>

        {usage && (
          <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
            {usage.model && <span className="font-mono">{usage.model}</span>}
            {usage.promptTokens !== undefined && (
              <span>输入 {usage.promptTokens.toLocaleString()}</span>
            )}
            {usage.completionTokens !== undefined && (
              <span>输出 {usage.completionTokens.toLocaleString()}</span>
            )}
            {usage.totalTokens !== undefined && (
              <span>总计 {usage.totalTokens.toLocaleString()} tokens</span>
            )}
          </div>
        )}

        {message.toolCalls && message.toolCalls.length > 0 && (
          <div className="mt-4 space-y-2 border-l-2 border-border/50 pl-4">
            <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground/60">
              工具调用
            </p>
            {message.toolCalls.map((toolCall) => (
              <div
                key={toolCall.id}
                className="rounded-lg border border-border/50 bg-secondary/30 p-3 font-mono text-sm"
              >
                <div className="flex items-center gap-2 text-primary">
                  <Terminal className="h-3.5 w-3.5" />
                  <span className="font-semibold">{toolCall.name}</span>
                </div>
                {Object.keys(toolCall.arguments).length > 0 && (
                  <pre className="mt-2 overflow-x-auto rounded-md bg-background/50 p-2 text-xs text-muted-foreground">
                    {JSON.stringify(toolCall.arguments, null, 2)}
                  </pre>
                )}
              </div>
            ))}
          </div>
        )}

        {runEvents && runEvents.length > 0 && (
          <div className="mt-4">
            <ProcessPanel events={runEvents} sessionId={sessionId} />
          </div>
        )}
      </div>
    </div>
  )
})

interface UsageSummary {
  model?: string
  promptTokens?: number
  completionTokens?: number
  totalTokens?: number
}

function getMessageUsage(message: Message): UsageSummary | null {
  const metadata = message.metadata
  const usage =
    metadata?.usage && typeof metadata.usage === 'object' && !Array.isArray(metadata.usage)
      ? (metadata.usage as Record<string, unknown>)
      : undefined

  const model = typeof metadata?.model === 'string' ? metadata.model : undefined
  const promptTokens = usage ? readNumber(usage, 'prompt_tokens') : undefined
  const completionTokens = usage ? readNumber(usage, 'completion_tokens') : undefined
  const usageTotal = usage ? readNumber(usage, 'total_tokens') : undefined
  const metadataTotal = metadata ? readNumber(metadata, 'totalTokens') : undefined
  const totalTokens = message.tokenCount ?? usageTotal ?? metadataTotal

  if (
    !model &&
    totalTokens === undefined &&
    promptTokens === undefined &&
    completionTokens === undefined
  ) {
    return null
  }

  return {
    model,
    promptTokens,
    completionTokens,
    totalTokens,
  }
}

function readNumber(source: Record<string, unknown>, key: string): number | undefined {
  const value = source[key]
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : undefined
  }
  return undefined
}
