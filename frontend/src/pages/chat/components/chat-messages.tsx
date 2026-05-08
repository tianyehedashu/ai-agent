import { useEffect, useRef } from 'react'

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
}

export default function ChatMessages({
  messages,
  streamingContent,
  isLoading,
  pendingToolCalls = [],
  processRuns = {},
  currentRunId = null,
  sessionId,
}: Readonly<ChatMessagesProps>): React.JSX.Element {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingContent, processRuns])

  // Empty state - 仅保留简短欢迎，不展示未实现的任务卡片
  if (messages.length === 0 && !isLoading) {
    return (
      <div className="flex h-full flex-col items-center justify-center px-4 py-8">
        <div className="text-center">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-primary/20 to-primary/5">
            <Bot className="h-7 w-7 text-primary" />
          </div>
          <h1 className="text-xl font-semibold tracking-tight text-foreground sm:text-2xl">
            有什么我可以帮你的？
          </h1>
          <p className="mt-1.5 text-sm text-muted-foreground">直接输入你的问题或需求即可</p>
        </div>
      </div>
    )
  }

  return (
    <ScrollArea className="h-full">
      <div className="mx-auto max-w-3xl space-y-6 px-4 py-6 sm:px-6 sm:py-8">
        {messages.map((message) => (
          <MessageBubble
            key={message.id}
            message={message}
            processRuns={processRuns}
            sessionId={sessionId}
          />
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
                    <ProcessPanel events={processRuns[currentRunId]} sessionId={sessionId} />
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

function MessageBubble({
  message,
  processRuns,
  sessionId,
}: Readonly<{
  message: Message
  processRuns: Record<string, ProcessEvent[]>
  sessionId?: string
}>): React.JSX.Element {
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
            <ProcessPanel events={runEvents} sessionId={sessionId} />
          </div>
        )}
      </div>
    </div>
  )
}
