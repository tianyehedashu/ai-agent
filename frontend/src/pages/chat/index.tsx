import { useEffect, useState, useCallback } from 'react'

import { History, Sparkles } from 'lucide-react'
import { useParams, useNavigate } from 'react-router-dom'

import { sessionApi } from '@/api/session'
import { InterruptDialog } from '@/components/chat/interrupt-dialog'
import { SessionNotice } from '@/components/chat/session-notice'
import { TimeTravelDebugger } from '@/components/chat/time-travel-debugger'
import { Button } from '@/components/ui/button'
import { useChat } from '@/hooks/use-chat'
import { useToast } from '@/hooks/use-toast'
import { useChatStore } from '@/stores/chat'

import ChatInput from './components/chat-input'
import ChatMessages from './components/chat-messages'
import { MCPSessionConfig } from './components/mcp-session-config'

export default function ChatPage(): React.JSX.Element {
  const { sessionId } = useParams<{ sessionId?: string }>()
  const navigate = useNavigate()
  const { toast } = useToast()
  const [showDebugger, setShowDebugger] = useState(false)
  const { setCurrentSession, input, setInput } = useChatStore()

  const {
    messages,
    isLoading,
    streamingContent,
    pendingToolCalls,
    interrupt,
    processRuns,
    currentRunId,
    sessionRecreation,
    sendMessage,
    resumeExecution,
    clearMessages,
    loadMessages,
    dismissSessionRecreation,
  } = useChat({
    sessionId,
    onError: (error) => {
      toast({
        title: '错误',
        description: error.message,
        variant: 'destructive',
      })
    },
  })

  // 处理会话访问错误（如 403 无权限），重定向到首页
  const handleSessionAccessError = useCallback(
    (error: unknown) => {
      const errorMessage = error instanceof Error ? error.message : '未知错误'
      const isPermissionError = errorMessage.includes('permission') || errorMessage.includes('403')

      if (isPermissionError) {
        toast({
          title: '无法访问该会话',
          description: '该会话可能已被删除或您没有访问权限，正在返回首页...',
          variant: 'destructive',
        })
        // 重定向到首页
        navigate('/chat', { replace: true })
      } else {
        toast({
          title: '加载失败',
          description: errorMessage,
          variant: 'destructive',
        })
      }
    },
    [toast, navigate]
  )

  // Load session - 当 sessionId 变化时，先清除消息再加载
  useEffect(() => {
    // 使用标志位来跟踪这个 effect 是否仍然有效
    // 当 sessionId 变化时，旧的 effect 会被清理，cancelled 会被设置为 true
    let cancelled = false

    // 每次 sessionId 变化都先清除消息
    clearMessages()

    if (sessionId) {
      // 加载会话信息
      sessionApi
        .get(sessionId)
        .then((session) => {
          // 只有当这个 effect 没有被取消时才更新状态
          if (!cancelled) {
            setCurrentSession(session)
          }
        })
        .catch((error: unknown) => {
          if (!cancelled) {
            console.error('Failed to load session:', error)
            handleSessionAccessError(error)
          }
        })

      // 加载历史消息
      sessionApi
        .getMessages(sessionId)
        .then((messages) => {
          // 只有当这个 effect 没有被取消时才更新状态
          if (!cancelled) {
            loadMessages(messages)
          }
        })
        .catch((error: unknown) => {
          // 如果加载失败，检查是否是权限问题
          // 只有当这个 effect 没有被取消时才处理错误
          if (!cancelled) {
            console.error('Failed to load messages:', error)
            handleSessionAccessError(error)
          }
        })
    } else {
      setCurrentSession(null)
    }

    // 清理函数：当 sessionId 变化或组件卸载时调用
    return () => {
      cancelled = true
    }
  }, [sessionId, setCurrentSession, clearMessages, loadMessages, handleSessionAccessError])

  const handleSend = async (): Promise<void> => {
    if (!input.trim() || isLoading) return
    const message = input.trim()
    setInput('')
    await sendMessage(message)
  }

  // 从检查点恢复
  const handleRestoreFromCheckpoint = async (checkpointId: string): Promise<void> => {
    await resumeExecution('approve')
    toast({
      title: '恢复执行',
      description: `正在从检查点 ${checkpointId.slice(0, 8)}... 恢复执行`,
    })
  }

  return (
    <div className="relative flex h-full flex-col">
      {/* Subtle header bar - only shows when in a session */}
      {sessionId && (
        <div className="absolute right-4 top-3 z-10 flex gap-2">
          <MCPSessionConfig sessionId={sessionId} />
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setShowDebugger(true)
            }}
            className="h-8 gap-1.5 rounded-full bg-background/80 px-3 text-xs text-muted-foreground shadow-sm backdrop-blur-sm hover:bg-background hover:text-foreground"
          >
            <History className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">时间旅行</span>
          </Button>
        </div>
      )}

      {/* Session Recreation Notice */}
      {sessionRecreation && (
        <div className="px-4 pt-4 sm:px-6">
          <div className="mx-auto max-w-3xl">
            <SessionNotice data={sessionRecreation} onDismiss={dismissSessionRecreation} />
          </div>
        </div>
      )}

      {/* Messages Area - Centered with max width */}
      <div className="flex-1 overflow-hidden">
        <ChatMessages
          messages={messages}
          streamingContent={streamingContent}
          isLoading={isLoading}
          pendingToolCalls={pendingToolCalls}
          processRuns={processRuns}
          currentRunId={currentRunId}
        />
      </div>

      {/* Input Area - Fixed at bottom with centered content */}
      <div className="relative z-10 border-t border-border/40 bg-background/95 pb-4 pt-2 backdrop-blur supports-[backdrop-filter]:bg-background/80">
        <div className="mx-auto max-w-3xl px-4">
          {/* Subtle branding when empty */}
          {messages.length === 0 && !isLoading && (
            <div className="mb-2 flex items-center justify-center gap-1.5 text-xs text-muted-foreground/50">
              <Sparkles className="h-3 w-3" />
              <span>AI Agent 助手</span>
            </div>
          )}
          <ChatInput value={input} onChange={setInput} onSend={handleSend} isLoading={isLoading} />
        </div>
      </div>

      {/* HITL Interrupt Dialog */}
      {interrupt && (
        <InterruptDialog
          open={true}
          pendingAction={interrupt.pendingAction}
          reason={interrupt.reason}
          onApprove={() => resumeExecution('approve')}
          onReject={() => resumeExecution('reject')}
          onModify={(args) => resumeExecution('modify', args)}
        />
      )}

      {/* Time Travel Debugger */}
      {sessionId && (
        <TimeTravelDebugger
          sessionId={sessionId}
          open={showDebugger}
          onOpenChange={setShowDebugger}
          onRestore={handleRestoreFromCheckpoint}
        />
      )}
    </div>
  )
}
