import { useEffect, useRef } from 'react'

import { User, Bot, Terminal, BookOpen, MessageSquare, Code2, Lightbulb } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism'

import { ProcessPanel } from '@/components/chat/process-panel'
import { ToolCallCard } from '@/components/chat/tool-call-card'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'
import type { Message, ProcessEvent, ToolCall } from '@/types'

interface ChatMessagesProps {
  messages: Message[]
  streamingContent: string
  isLoading: boolean
  pendingToolCalls?: ToolCall[]
  processRuns?: Record<string, ProcessEvent[]>
  currentRunId?: string | null
}

export default function ChatMessages({
  messages,
  streamingContent,
  isLoading,
  pendingToolCalls = [],
  processRuns = {},
  currentRunId = null,
}: Readonly<ChatMessagesProps>): React.JSX.Element {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingContent, processRuns])

  // Empty state - Welcome screen
  if (messages.length === 0 && !isLoading) {
    return (
      <div className="flex h-full flex-col items-center justify-center px-4 py-8">
        <div className="w-full max-w-2xl">
          {/* Hero */}
          <div className="mb-12 text-center">
            <div className="relative mx-auto mb-6 inline-flex">
              <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-primary/20 to-primary/5 shadow-lg">
                <Bot className="h-8 w-8 text-primary" />
              </div>
              <div className="absolute -right-1 -top-1 h-4 w-4 rounded-full bg-green-500 ring-4 ring-background" />
            </div>
            <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
              有什么我可以帮你的？
            </h1>
            <p className="mt-2 text-muted-foreground">
              编写代码、分析数据、回答问题，或者只是聊聊天
            </p>
          </div>

          {/* Suggestions Grid */}
          <div className="grid gap-3 sm:grid-cols-2">
            <SuggestionCard
              icon={<Code2 className="h-4 w-4" />}
              iconColor="text-blue-500"
              title="编写 Python 脚本"
              description="处理数据并生成可视化图表"
            />
            <SuggestionCard
              icon={<Lightbulb className="h-4 w-4" />}
              iconColor="text-amber-500"
              title="解释技术概念"
              description="用简单易懂的方式理解复杂话题"
            />
            <SuggestionCard
              icon={<BookOpen className="h-4 w-4" />}
              iconColor="text-emerald-500"
              title="总结长文档"
              description="提取关键信息和核心观点"
            />
            <SuggestionCard
              icon={<MessageSquare className="h-4 w-4" />}
              iconColor="text-violet-500"
              title="润色文案内容"
              description="优化邮件、报告或其他文字"
            />
          </div>
        </div>
      </div>
    )
  }

  return (
    <ScrollArea className="h-full">
      <div className="mx-auto max-w-3xl space-y-6 px-4 py-6 sm:px-6 sm:py-8">
        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} processRuns={processRuns} />
        ))}

        {/* Streaming content with live process panel */}
        {(currentRunId !== null || isLoading) && (
          <div className="group flex items-start gap-3 animate-in fade-in slide-in-from-bottom-2">
            <Avatar className="mt-0.5 h-8 w-8 shrink-0 border shadow-sm">
              <AvatarFallback className="bg-gradient-to-br from-primary/20 to-primary/5">
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
                    <ProcessPanel events={processRuns[currentRunId]} />
                  </div>
                )}

              {!streamingContent && pendingToolCalls.length === 0 && (
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

function SuggestionCard({
  icon,
  iconColor,
  title,
  description,
}: {
  icon: React.ReactNode
  iconColor: string
  title: string
  description: string
}): React.JSX.Element {
  return (
    <button className="group flex items-start gap-3 rounded-xl border border-border/40 bg-secondary/20 p-4 text-left transition-all hover:border-border/80 hover:bg-secondary/40 hover:shadow-sm">
      <div
        className={cn(
          'flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-background shadow-sm ring-1 ring-border/20 transition-colors',
          iconColor
        )}
      >
        {icon}
      </div>
      <div className="min-w-0">
        <p className="font-medium leading-none text-foreground/90">{title}</p>
        <p className="mt-1 text-sm text-muted-foreground">{description}</p>
      </div>
    </button>
  )
}

function MessageBubble({
  message,
  processRuns,
}: Readonly<{ message: Message; processRuns: Record<string, ProcessEvent[]> }>): React.JSX.Element {
  const isUser = message.role === 'user'
  const runId = message.metadata?.runId as string | undefined
  const runEvents = runId ? processRuns[runId] : undefined

  if (isUser) {
    return (
      <div className="flex items-start justify-end gap-3 animate-in fade-in slide-in-from-bottom-2">
        <div className="max-w-[85%] sm:max-w-[75%]">
          <div className="rounded-2xl rounded-br-md bg-secondary px-4 py-3 text-secondary-foreground shadow-sm">
            <div className="text-[15px] leading-relaxed">
              <ReactMarkdown>{message.content}</ReactMarkdown>
            </div>
          </div>
        </div>
        <Avatar className="mt-0.5 h-8 w-8 shrink-0 border shadow-sm">
          <AvatarFallback className="bg-secondary">
            <User className="h-4 w-4" />
          </AvatarFallback>
        </Avatar>
      </div>
    )
  }

  return (
    <div className="group flex items-start gap-3 animate-in fade-in slide-in-from-bottom-2">
      <Avatar className="mt-0.5 h-8 w-8 shrink-0 border shadow-sm">
        <AvatarFallback className="bg-gradient-to-br from-primary/20 to-primary/5">
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
            <ProcessPanel events={runEvents} />
          </div>
        )}
      </div>
    </div>
  )
}
