import { useEffect, useRef } from 'react'
import { cn } from '@/lib/utils'
import { User, Bot } from 'lucide-react'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import type { Message } from '@/types'
import ReactMarkdown from 'react-markdown'

import type { ToolCall } from '@/types'
import { ToolCallCard } from '@/components/chat/tool-call-card'

interface ChatMessagesProps {
  messages: Message[]
  streamingContent: string
  isLoading: boolean
  pendingToolCalls?: ToolCall[]
}

export default function ChatMessages({
  messages,
  streamingContent,
  isLoading,
  pendingToolCalls = [],
}: ChatMessagesProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingContent])

  if (messages.length === 0 && !isLoading) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center p-8">
        <Bot className="h-16 w-16 text-muted-foreground/50 mb-4" />
        <h2 className="text-xl font-semibold mb-2">开始新对话</h2>
        <p className="text-muted-foreground text-center max-w-md">
          输入您的问题或任务，AI Agent 将帮助您完成。
        </p>
      </div>
    )
  }

  return (
    <ScrollArea className="flex-1 p-4">
      <div className="mx-auto max-w-3xl space-y-6">
        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}

        {/* Streaming content */}
        {streamingContent && (
          <MessageBubble
            message={{
              id: 'streaming',
              role: 'assistant',
              content: streamingContent,
              createdAt: new Date().toISOString(),
            }}
          />
        )}

        {/* Pending Tool Calls */}
        {pendingToolCalls.length > 0 && (
          <div className="space-y-2">
            {pendingToolCalls.map((tc) => (
              <ToolCallCard key={tc.id} toolCall={tc} isPending />
            ))}
          </div>
        )}

        {/* Loading indicator */}
        {isLoading && !streamingContent && pendingToolCalls.length === 0 && (
          <div className="flex items-start gap-4">
            <Avatar className="h-8 w-8 bg-primary/10">
              <AvatarFallback>
                <Bot className="h-4 w-4" />
              </AvatarFallback>
            </Avatar>
            <div className="typing-indicator pt-3">
              <span />
              <span />
              <span />
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>
    </ScrollArea>
  )
}

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === 'user'

  return (
    <div
      className={cn(
        "flex items-start gap-4 animate-in",
        isUser && "flex-row-reverse"
      )}
    >
      <Avatar className={cn(
        "h-8 w-8",
        isUser ? "bg-primary" : "bg-primary/10"
      )}>
        <AvatarFallback>
          {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
        </AvatarFallback>
      </Avatar>

      <div
        className={cn(
          "flex-1 rounded-lg px-4 py-3",
          isUser
            ? "bg-primary text-primary-foreground"
            : "bg-muted"
        )}
      >
        {message.content && (
          <div className="markdown-body prose prose-sm dark:prose-invert max-w-none">
            <ReactMarkdown>{message.content}</ReactMarkdown>
          </div>
        )}

        {message.toolCalls && message.toolCalls.length > 0 && (
          <div className="mt-2 space-y-2">
            {message.toolCalls.map((toolCall) => (
              <div
                key={toolCall.id}
                className="rounded border bg-background/50 p-2 text-xs font-mono"
              >
                <span className="text-muted-foreground">调用工具: </span>
                <span className="text-primary">{toolCall.name}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
