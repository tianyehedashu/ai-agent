/**
 * Chat Hook - 聊天功能 Hook
 *
 * 封装聊天相关的状态和逻辑
 */

import { useState, useCallback, useRef, useEffect } from 'react'

import { useQueryClient } from '@tanstack/react-query'

import { chatApi } from '@/api/chat'
import { generateId } from '@/lib/utils'
import type { ChatEvent, Message, ProcessEvent, SessionRecreationData, ToolCall } from '@/types'

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
  currentRunId: string | null
  sessionRecreation: SessionRecreationData | null
  sendMessage: (content: string) => Promise<void>
  cancelRequest: () => void // 取消当前请求
  resumeExecution: (
    action: 'approve' | 'reject' | 'modify',
    modifiedArgs?: Record<string, unknown>
  ) => Promise<void>
  clearMessages: () => void
  loadMessages: (messages: Message[]) => void // 加载历史消息
  dismissSessionRecreation: () => void
}

interface InterruptState {
  checkpointId: string
  pendingAction: ToolCall
  reason: string
}

export function useChat(options: UseChatOptions = {}): UseChatReturn {
  const { sessionId: initialSessionId, agentId, onError } = options
  const queryClient = useQueryClient()

  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [streamingContent, setStreamingContent] = useState('')
  const [pendingToolCalls, setPendingToolCalls] = useState<ToolCall[]>([])
  const [interrupt, setInterrupt] = useState<InterruptState | null>(null)
  const [processRuns, setProcessRuns] = useState<Record<string, ProcessEvent[]>>({})
  const [currentRunId, setCurrentRunId] = useState<string | null>(null)
  const [sessionRecreation, setSessionRecreation] = useState<SessionRecreationData | null>(null)

  const sessionIdRef = useRef<string | undefined>(initialSessionId)
  const currentToolCallsRef = useRef<ToolCall[]>([])
  const currentRunIdRef = useRef<string | null>(null)
  const abortControllerRef = useRef<AbortController | null>(null)

  // 同步 sessionId 变化
  useEffect(() => {
    sessionIdRef.current = initialSessionId
  }, [initialSessionId])

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
            // 刷新会话列表，以便显示新创建的会话
            void queryClient.invalidateQueries({ queryKey: ['sessions'] })
          }
          break
        }

        case 'session_recreated': {
          // 会话沙箱环境被重建（之前的容器已被清理）
          const recreationData = event.data as {
            session_id?: string
            is_new?: boolean
            is_recreated?: boolean
            previous_state?: {
              session_id?: string
              cleaned_at?: string
              cleanup_reason?: string
              packages_installed?: string[]
              files_created?: string[]
              command_count?: number
              total_duration_ms?: number
            } | null
            message?: string | null
          }

          // 转换为前端格式（snake_case -> camelCase）
          const sessionRecreationInfo: SessionRecreationData = {
            sessionId: recreationData.session_id ?? '',
            isNew: recreationData.is_new ?? false,
            isRecreated: recreationData.is_recreated ?? false,
            previousState: recreationData.previous_state
              ? {
                  sessionId: recreationData.previous_state.session_id ?? '',
                  cleanedAt: recreationData.previous_state.cleaned_at ?? '',
                  cleanupReason: recreationData.previous_state.cleanup_reason ?? '',
                  packagesInstalled: recreationData.previous_state.packages_installed ?? [],
                  filesCreated: recreationData.previous_state.files_created ?? [],
                  commandCount: recreationData.previous_state.command_count ?? 0,
                  totalDurationMs: recreationData.previous_state.total_duration_ms ?? 0,
                }
              : null,
            message: recreationData.message ?? null,
          }

          // 只有当是重建（有历史记录）时才显示提示
          if (sessionRecreationInfo.isRecreated && sessionRecreationInfo.previousState) {
            setSessionRecreation(sessionRecreationInfo)
          }
          break
        }

        case 'title_updated': {
          // 标题已更新，刷新会话列表和当前会话信息
          const titleData = event.data as { session_id?: string; title?: string }
          if (titleData.session_id) {
            // 刷新会话列表，以便显示更新后的标题
            void queryClient.invalidateQueries({ queryKey: ['sessions'] })
            // 如果当前会话的标题被更新，更新当前会话信息
            if (sessionIdRef.current === titleData.session_id && titleData.title) {
              void queryClient.invalidateQueries({ queryKey: ['session', titleData.session_id] })
            }
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
          // 后端发送: { tool_call_id, tool_name, arguments }
          const toolCallData = event.data as {
            tool_call_id?: string
            tool_name?: string
            arguments?: Record<string, unknown>
          }
          // 转换为内部 ToolCall 格式
          const toolCall: ToolCall = {
            id: toolCallData.tool_call_id ?? generateId(),
            name: toolCallData.tool_name ?? 'unknown',
            arguments: toolCallData.arguments ?? {},
          }
          currentToolCallsRef.current.push(toolCall)
          setPendingToolCalls([...currentToolCallsRef.current])
          if (currentRunIdRef.current) {
            appendProcessEvent(currentRunIdRef.current, {
              id: generateId(),
              kind: 'tool_call',
              timestamp: event.timestamp,
              // 传递完整的后端数据（包含 tool_name 和 arguments）
              payload: event.data,
            })
          }
          break
        }

        case 'tool_result': {
          // 后端发送: { tool_call_id, tool_name, success, output, error, duration_ms }
          // 注意：后端使用 snake_case (tool_call_id)
          const resultData = event.data as { tool_call_id?: string; toolCallId?: string }
          const toolCallId = resultData.tool_call_id ?? resultData.toolCallId
          // 工具执行完成，清除对应的 pending
          currentToolCallsRef.current = currentToolCallsRef.current.filter(
            (tc) => tc.id !== toolCallId
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
          currentRunIdRef.current = null
          setCurrentRunId(null)
          setIsLoading(false)

          // 对话完成后刷新会话列表，以便显示可能已生成的标题
          // 标题生成是异步的，可能在对话完成后才完成
          if (sessionIdRef.current) {
            // 延迟一点刷新，给标题生成留出时间
            setTimeout(() => {
              void queryClient.invalidateQueries({ queryKey: ['sessions'] })
            }, 1000)
          }
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
    [appendProcessEvent, onError, queryClient]
  )

  const cancelRequest = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
      setIsLoading(false)
      setStreamingContent('')
      currentToolCallsRef.current = []
      currentRunIdRef.current = null
      setCurrentRunId(null)
    }
  }, [])

  const sendMessage = useCallback(
    async (content: string) => {
      if (!content.trim() || isLoading) return

      // 取消之前的请求（如果有）
      if (abortControllerRef.current) {
        abortControllerRef.current.abort()
      }

      // 创建新的 AbortController
      const abortController = new AbortController()
      abortControllerRef.current = abortController

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
      setCurrentRunId(runId)
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
            // 忽略取消导致的错误
            if (error.name !== 'AbortError') {
              onError?.(error)
            }
            setIsLoading(false)
          },
          () => {
            setIsLoading(false)
            abortControllerRef.current = null
          },
          abortController.signal
        )
      } catch (error) {
        // 忽略取消导致的错误
        if ((error as Error).name !== 'AbortError') {
          onError?.(error as Error)
        }
        setIsLoading(false)
        abortControllerRef.current = null
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
    setCurrentRunId(null)
    setProcessRuns({})
    setSessionRecreation(null)
  }, [])

  const loadMessages = useCallback((messages: Message[]) => {
    setMessages(messages)
    setStreamingContent('')
    setPendingToolCalls([])
    setInterrupt(null)
    currentToolCallsRef.current = []
    currentRunIdRef.current = null
    setCurrentRunId(null)
    // 不清除 processRuns，因为历史消息可能关联到已有的 processRuns
    // 不清除 sessionRecreation，因为这是会话级别的信息
  }, [])

  const dismissSessionRecreation = useCallback(() => {
    setSessionRecreation(null)
  }, [])

  return {
    messages,
    isLoading,
    streamingContent,
    pendingToolCalls,
    interrupt,
    processRuns,
    currentRunId,
    sessionRecreation,
    sendMessage,
    cancelRequest,
    resumeExecution,
    clearMessages,
    loadMessages,
    dismissSessionRecreation,
  }
}
