import { useEffect, useState, useCallback } from 'react'

import { History } from 'lucide-react'
import { useParams } from 'react-router-dom'

import { sessionApi } from '@/api/session'
import { InterruptDialog } from '@/components/chat/interrupt-dialog'
import { TimeTravelDebugger } from '@/components/chat/time-travel-debugger'
import { Button } from '@/components/ui/button'
import { useChat } from '@/hooks/use-chat'
import { useToast } from '@/hooks/use-toast'
import { useChatStore } from '@/stores/chat'

import ChatInput from './components/chat-input'
import ChatMessages from './components/chat-messages'
import ChatSidebar from './components/chat-sidebar'

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
    sendMessage,
    resumeExecution,
    clearMessages,
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

  // Load session
  useEffect(() => {
    if (sessionId) {
      void loadSession(sessionId)
    } else {
      setCurrentSession(null)
      clearMessages()
    }
  }, [sessionId, loadSession, setCurrentSession, clearMessages])

  const handleSend = async (): Promise<void> => {
    if (!input.trim() || isLoading) return
    const message = input.trim()
    setInput('')
    await sendMessage(message)
  }

  // 从检查点恢复
  const handleRestoreFromCheckpoint = async (checkpointId: string): Promise<void> => {
    // 触发从检查点恢复
    await resumeExecution('approve')
    toast({
      title: '恢复执行',
      description: `正在从检查点 ${checkpointId.slice(0, 8)}... 恢复执行`,
    })
  }

  return (
    <div className="flex h-full">
      {/* Chat Sidebar */}
      <ChatSidebar />

      {/* Main Chat Area */}
      <div className="flex flex-1 flex-col">
        {/* Header with Debug Button */}
        {sessionId && (
          <div className="flex items-center justify-end border-b px-4 py-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setShowDebugger(true)
              }}
              className="text-muted-foreground hover:text-foreground"
            >
              <History className="mr-2 h-4 w-4" />
              时间旅行调试
            </Button>
          </div>
        )}

        {/* Messages */}
        <ChatMessages
          messages={messages}
          streamingContent={streamingContent}
          isLoading={isLoading}
          pendingToolCalls={pendingToolCalls}
          processRuns={processRuns}
          currentRunId={currentRunId}
        />

        {/* Input */}
        <ChatInput value={input} onChange={setInput} onSend={handleSend} isLoading={isLoading} />
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
