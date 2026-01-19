import { useEffect, useState, useCallback } from 'react'

import { History, Sparkles } from 'lucide-react'
import { useParams } from 'react-router-dom'

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

export default function ChatPage(): React.JSX.Element {
  const { sessionId } = useParams<{ sessionId?: string }>()
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

  const loadSession = useCallback(
    async (id: string) => {
      try {
        const session = await sessionApi.get(id)
        setCurrentSession(session)
      } catch (error) {
        console.error('Failed to load session:', error)
      }
    },
    [setCurrentSession]
  )

  // Load session - 当 sessionId 变化时，先清除消息再加载
  useEffect(() => {
    // 每次 sessionId 变化都先清除消息
    clearMessages()
    
    if (sessionId) {
      void loadSession(sessionId)
      // 加载历史消息
      sessionApi
        .getMessages(sessionId)
        .then((messages) => {
          loadMessages(messages)
        })
        .catch((error) => {
          // 如果加载失败，只记录错误，不影响会话信息加载
          console.error('Failed to load messages:', error)
          toast({
            title: '加载消息失败',
            description: error instanceof Error ? error.message : '未知错误',
            variant: 'destructive',
          })
        })
    } else {
      setCurrentSession(null)
    }
  }, [sessionId, loadSession, setCurrentSession, clearMessages, loadMessages])

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
        <div className="absolute right-4 top-3 z-10">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowDebugger(true)}
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
      <div className="relative border-t border-border/40 bg-gradient-to-t from-background via-background to-transparent pb-4 pt-2">
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
