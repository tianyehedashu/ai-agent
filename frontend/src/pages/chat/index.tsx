import { useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { useChatStore } from '@/stores/chat'
import { sessionApi } from '@/api/session'
import { useChat } from '@/hooks/use-chat'
import { useToast } from '@/hooks/use-toast'
import ChatMessages from './components/chat-messages'
import ChatInput from './components/chat-input'
import ChatSidebar from './components/chat-sidebar'
import { InterruptDialog } from '@/components/chat/interrupt-dialog'

export default function ChatPage() {
  const { sessionId } = useParams<{ sessionId?: string }>()
  const { toast } = useToast()
  const {
    currentSession,
    setCurrentSession,
    clearMessages: clearStoreMessages,
    input,
    setInput,
  } = useChatStore()

  const {
    messages,
    isLoading,
    streamingContent,
    pendingToolCalls,
    interrupt,
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

  // Load session
  useEffect(() => {
    if (sessionId) {
      loadSession(sessionId)
    } else {
      setCurrentSession(null)
      clearMessages()
    }
  }, [sessionId])

  const loadSession = async (id: string) => {
    try {
      const session = await sessionApi.get(id)
      setCurrentSession(session)
    } catch (error) {
      console.error('Failed to load session:', error)
    }
  }

  const handleSend = async () => {
    if (!input.trim() || isLoading) return
    const message = input.trim()
    setInput('')
    await sendMessage(message)
  }

  return (
    <div className="flex h-full">
      {/* Chat Sidebar */}
      <ChatSidebar />

      {/* Main Chat Area */}
      <div className="flex flex-1 flex-col">
        {/* Messages */}
        <ChatMessages
          messages={messages}
          streamingContent={streamingContent}
          isLoading={isLoading}
          pendingToolCalls={pendingToolCalls}
        />

        {/* Input */}
        <ChatInput
          value={input}
          onChange={setInput}
          onSend={handleSend}
          isLoading={isLoading}
        />
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
    </div>
  )
}
