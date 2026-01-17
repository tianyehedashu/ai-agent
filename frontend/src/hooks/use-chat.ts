/**
 * Chat Hook - 聊天功能 Hook
 *
 * 封装聊天相关的状态和逻辑
 */

import { useState, useCallback, useRef } from 'react'

import { chatApi } from '@/api/chat'
import { generateId } from '@/lib/utils'
import type { ChatEvent, Message, ProcessEvent, ToolCall } from '@/types'

interface UseChatOptions {
  sessionId?: string
  agentId?: string
  onError?: (error: Error) => void
}

interface UseChatReturn {
  messages: Message[]
  isLoading: boolean
  streamingContent: string
  pendingToolCalls: ToolCall[]
  interrupt: InterruptState | null
  processRuns: Record<string, ProcessEvent[]>
  sendMessage: (content: string) => Promise<void>
  resumeExecution: (
    action: 'approve' | 'reject' | 'modify',
    modifiedArgs?: Record<string, unknown>
  ) => Promise<void>
  clearMessages: () => void
}

interface InterruptState {
  checkpointId: string
  pendingAction: ToolCall
  reason: string
}

export function useChat(options: UseChatOptions = {}): UseChatReturn {
  const { sessionId: initialSessionId, agentId, onError } = options

  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [streamingContent, setStreamingContent] = useState('')
  const [pendingToolCalls, setPendingToolCalls] = useState<ToolCall[]>([])
  const [interrupt, setInterrupt] = useState<InterruptState | null>(null)
  const [processRuns, setProcessRuns] = useState<Record<string, ProcessEvent[]>>({})

  const sessionIdRef = useRef<string | undefined>(initialSessionId)
  const currentToolCallsRef = useRef<ToolCall[]>([])
  const currentRunIdRef = useRef<string | null>(null)

  const appendProcessEvent = useCallback((runId: string, event: ProcessEvent) => {
    setProcessRuns((prev) => ({
      ...prev,
      [runId]: [...(prev[runId] ?? []), event],
    }))
  }, [])

  const handleEvent = useCallback(
    (event: ChatEvent) => {
      switch (event.type) {
        case 'session_created': {
          // 保存新创建的会话 ID，用于后续消息的上下文关联
          const sessionData = event.data as { session_id?: string }
          if (sessionData.session_id) {
            sessionIdRef.current = sessionData.session_id
          }
          break
        }

        case 'thinking': {
          // 显示思考状态
          if (currentRunIdRef.current) {
            appendProcessEvent(currentRunIdRef.current, {
              id: generateId(),
              kind: 'thinking',
              timestamp: event.timestamp,
              payload: event.data,
            })
          }
          break
        }

        case 'text': {
          const textData = event.data as { content?: string }
          if (textData.content) {
            setStreamingContent((prev) => prev + (textData.content ?? ''))
            if (currentRunIdRef.current) {
              appendProcessEvent(currentRunIdRef.current, {
                id: generateId(),
                kind: 'text',
                timestamp: event.timestamp,
                payload: textData,
              })
            }
          }
          break
        }

        case 'tool_call': {
          const toolCallData = event.data as unknown as ToolCall
          currentToolCallsRef.current.push(toolCallData)
          setPendingToolCalls([...currentToolCallsRef.current])
          if (currentRunIdRef.current) {
            appendProcessEvent(currentRunIdRef.current, {
              id: generateId(),
              kind: 'tool_call',
              timestamp: event.timestamp,
              payload: toolCallData as unknown as Record<string, unknown>,
            })
          }
          break
        }

        case 'tool_result': {
          // 工具执行完成，清除对应的 pending
          const resultData = event.data as { toolCallId: string }
          currentToolCallsRef.current = currentToolCallsRef.current.filter(
            (tc) => tc.id !== resultData.toolCallId
          )
          setPendingToolCalls([...currentToolCallsRef.current])
          if (currentRunIdRef.current) {
            appendProcessEvent(currentRunIdRef.current, {
              id: generateId(),
              kind: 'tool_result',
              timestamp: event.timestamp,
              payload: event.data,
            })
          }
          break
        }

        case 'interrupt': {
          const interruptData = event.data as unknown as InterruptState
          setInterrupt(interruptData)
          setIsLoading(false)
          if (currentRunIdRef.current) {
            appendProcessEvent(currentRunIdRef.current, {
              id: generateId(),
              kind: 'interrupt',
              timestamp: event.timestamp,
              payload: event.data,
            })
          }
          break
        }

        case 'done': {
          const doneData = event.data as { final_message?: { content?: string } }
          const finalContent = doneData.final_message?.content ?? ''
          const runId = currentRunIdRef.current

          // 添加助手消息
          if (finalContent) {
            const assistantMessage: Message = {
              id: generateId(),
              role: 'assistant',
              content: finalContent,
              metadata: runId ? { runId } : undefined,
              createdAt: new Date().toISOString(),
            }
            setMessages((prev) => [...prev, assistantMessage])
          }

          if (runId) {
            appendProcessEvent(runId, {
              id: generateId(),
              kind: 'done',
              timestamp: event.timestamp,
              payload: event.data,
            })
          }

          setStreamingContent('')
          setPendingToolCalls([])
          currentToolCallsRef.current = []
          setIsLoading(false)
          break
        }

        case 'error': {
          const errorData = event.data as { error: string }
          onError?.(new Error(errorData.error))
          setIsLoading(false)
          if (currentRunIdRef.current) {
            appendProcessEvent(currentRunIdRef.current, {
              id: generateId(),
              kind: 'error',
              timestamp: event.timestamp,
              payload: errorData as unknown as Record<string, unknown>,
            })
          }
          break
        }

        case 'terminated': {
          setIsLoading(false)
          break
        }
      }
    },
    [appendProcessEvent, onError]
  )

  const sendMessage = useCallback(
    async (content: string) => {
      if (!content.trim() || isLoading) return

      // 添加用户消息
      const userMessage: Message = {
        id: generateId(),
        role: 'user',
        content: content.trim(),
        createdAt: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, userMessage])

      // 重置状态
      setIsLoading(true)
      setStreamingContent('')
      setInterrupt(null)
      currentToolCallsRef.current = []
      const runId = generateId()
      currentRunIdRef.current = runId
      setProcessRuns((prev) => ({ ...prev, [runId]: [] }))

      try {
        await chatApi.sendMessage(
          {
            message: content,
            sessionId: sessionIdRef.current,
            agentId,
          },
          handleEvent,
          (error) => {
            onError?.(error)
            setIsLoading(false)
          },
          () => {
            setIsLoading(false)
          }
        )
      } catch (error) {
        onError?.(error as Error)
        setIsLoading(false)
      }
    },
    [isLoading, agentId, handleEvent, onError]
  )

  const resumeExecution = useCallback(
    async (action: 'approve' | 'reject' | 'modify', modifiedArgs?: Record<string, unknown>) => {
      if (!interrupt || !sessionIdRef.current) return

      setIsLoading(true)
      setInterrupt(null)

      try {
        await chatApi.resume(
          sessionIdRef.current,
          {
            checkpointId: interrupt.checkpointId,
            action,
            modifiedArgs,
          },
          handleEvent,
          (error) => {
            onError?.(error)
            setIsLoading(false)
          },
          () => {
            setIsLoading(false)
          }
        )
      } catch (error) {
        onError?.(error as Error)
        setIsLoading(false)
      }
    },
    [interrupt, handleEvent, onError]
  )

  const clearMessages = useCallback(() => {
    setMessages([])
    setStreamingContent('')
    setPendingToolCalls([])
    setInterrupt(null)
    currentToolCallsRef.current = []
    currentRunIdRef.current = null
    setProcessRuns({})
  }, [])

  return {
    messages,
    isLoading,
    streamingContent,
    pendingToolCalls,
    interrupt,
    processRuns,
    sendMessage,
    resumeExecution,
    clearMessages,
  }
}
