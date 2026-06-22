/**
 * Chat Hook - 聊天功能 Hook
 *
 * 封装聊天相关的状态和逻辑；按会话隔离运行时状态，切换会话时后台 SSE 可继续执行。
 */

import {
  startTransition,
  useState,
  useCallback,
  useRef,
  useEffect,
  type MutableRefObject,
} from 'react'

import { useQueryClient } from '@tanstack/react-query'

import { chatApi } from '@/api/chat'
import { generateId } from '@/lib/utils'
import { useChatStore } from '@/stores/chat'
import type { ChatEvent, Message, ProcessEvent, SessionRecreationData, ToolCall } from '@/types'

/** 无 sessionId 的新对话草稿键 */
const DRAFT_SESSION_KEY = '__draft__'

function toSessionKey(sessionId: string | undefined): string {
  return sessionId ?? DRAFT_SESSION_KEY
}

interface SessionChatRuntime {
  messages: Message[]
  processRuns: Record<string, ProcessEvent[]>
  isLoading: boolean
  streamingContent: string
  pendingToolCalls: ToolCall[]
  interrupt: InterruptState | null
  currentRunId: string | null
  sessionRecreation: SessionRecreationData | null
  currentRunIdValue: string | null
  streamingContentValue: string
  currentToolCalls: ToolCall[]
}

function createEmptyRuntime(): SessionChatRuntime {
  return {
    messages: [],
    processRuns: {},
    isLoading: false,
    streamingContent: '',
    pendingToolCalls: [],
    interrupt: null,
    currentRunId: null,
    sessionRecreation: null,
    currentRunIdValue: null,
    streamingContentValue: '',
    currentToolCalls: [],
  }
}

interface UseChatOptions {
  sessionId?: string
  agentId?: string
  onError?: (error: Error) => void
  /** 首次发消息后服务端创建会话时回调，用于更新 URL 等（如 navigate(`/chat/${id}`)） */
  onSessionCreated?: (sessionId: string) => void
  /** 流式进行中的 sessionId 集合；由父组件传入以便跳过历史拉取竞态 */
  activeStreamSessionsRef?: MutableRefObject<Set<string>>
  /** SSE 流结束（done / error / cancel）时回调 */
  onStreamEnd?: (sessionId: string | undefined) => void
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
  sendMessage: (
    content: string,
    options?: {
      modelRef?: string | null
      gatewayTeamId?: string
      gatewayVerboseRequestLog?: boolean
      creativeMode?: 'chat' | 'image_gen'
      referenceImageUrls?: string[]
      imageGenStrength?: number | null
    }
  ) => Promise<void>
  cancelRequest: () => void
  resumeExecution: (
    action: 'approve' | 'reject' | 'modify',
    modifiedArgs?: Record<string, unknown>
  ) => Promise<void>
  clearMessages: () => void
  loadMessages: (messages: Message[]) => void
  /** 切换当前视图会话（保留其他会话内存状态与后台流） */
  switchViewSession: (sessionId: string | undefined) => void
  /** 重置草稿新对话（仅中止草稿会话上的流） */
  resetDraftChat: () => void
  dismissSessionRecreation: () => void
}

interface InterruptState {
  checkpointId: string
  pendingAction: ToolCall
  reason: string
}

export function useChat(options: UseChatOptions = {}): UseChatReturn {
  const {
    sessionId: initialSessionId,
    agentId,
    onError,
    onSessionCreated,
    activeStreamSessionsRef,
    onStreamEnd,
  } = options
  const queryClient = useQueryClient()

  const onErrorRef = useRef(onError)
  const onSessionCreatedRef = useRef(onSessionCreated)
  const onStreamEndRef = useRef(onStreamEnd)
  onErrorRef.current = onError
  onSessionCreatedRef.current = onSessionCreated
  onStreamEndRef.current = onStreamEnd

  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [streamingContent, setStreamingContent] = useState('')
  const [pendingToolCalls, setPendingToolCalls] = useState<ToolCall[]>([])
  const [interrupt, setInterrupt] = useState<InterruptState | null>(null)
  const [processRuns, setProcessRuns] = useState<Record<string, ProcessEvent[]>>({})
  const [currentRunId, setCurrentRunId] = useState<string | null>(null)
  const [sessionRecreation, setSessionRecreation] = useState<SessionRecreationData | null>(null)

  const runtimeMapRef = useRef<Map<string, SessionChatRuntime>>(new Map())
  const abortMapRef = useRef<Map<string, AbortController>>(new Map())

  const sessionIdRef = useRef<string | undefined>(initialSessionId)
  const viewKeyRef = useRef<string>(toSessionKey(initialSessionId))
  const streamKeyRef = useRef<string>(toSessionKey(initialSessionId))

  const getRuntime = useCallback((key: string): SessionChatRuntime => {
    const map = runtimeMapRef.current
    let runtime = map.get(key)
    if (!runtime) {
      runtime = createEmptyRuntime()
      map.set(key, runtime)
    }
    return runtime
  }, [])

  const applyRuntimeToReact = useCallback((runtime: SessionChatRuntime) => {
    setMessages(runtime.messages)
    setProcessRuns(runtime.processRuns)
    setIsLoading(runtime.isLoading)
    setStreamingContent(runtime.streamingContent)
    setPendingToolCalls(runtime.pendingToolCalls)
    setInterrupt(runtime.interrupt)
    setCurrentRunId(runtime.currentRunId)
    setSessionRecreation(runtime.sessionRecreation)
  }, [])

  const syncViewToReact = useCallback(() => {
    applyRuntimeToReact(getRuntime(viewKeyRef.current))
  }, [applyRuntimeToReact, getRuntime])

  const migrateRuntimeKey = useCallback((fromKey: string, toKey: string) => {
    if (fromKey === toKey) return
    const map = runtimeMapRef.current
    const runtime = map.get(fromKey)
    if (runtime) {
      map.set(toKey, runtime)
      map.delete(fromKey)
    }
    const abort = abortMapRef.current.get(fromKey)
    if (abort) {
      abortMapRef.current.set(toKey, abort)
      abortMapRef.current.delete(fromKey)
    }
    if (streamKeyRef.current === fromKey) {
      streamKeyRef.current = toKey
    }
    if (viewKeyRef.current === fromKey) {
      viewKeyRef.current = toKey
    }
  }, [])

  // 同步 URL sessionId → 视图会话
  useEffect(() => {
    const nextKey = toSessionKey(initialSessionId)
    if (viewKeyRef.current === nextKey) {
      sessionIdRef.current = initialSessionId
      return
    }
    viewKeyRef.current = nextKey
    sessionIdRef.current = initialSessionId
    syncViewToReact()
  }, [initialSessionId, syncViewToReact])

  const markStreamActive = useCallback(
    (activeSessionId: string | undefined) => {
      if (activeSessionId) {
        activeStreamSessionsRef?.current.add(activeSessionId)
      }
    },
    [activeStreamSessionsRef]
  )

  const finishStream = useCallback(
    (endedSessionId: string | undefined) => {
      if (endedSessionId) {
        activeStreamSessionsRef?.current.delete(endedSessionId)
      }
      onStreamEndRef.current?.(endedSessionId)
    },
    [activeStreamSessionsRef]
  )

  const appendProcessEvent = useCallback(
    (runtime: SessionChatRuntime, runId: string, event: ProcessEvent) => {
      runtime.processRuns = {
        ...runtime.processRuns,
        [runId]: [...(runtime.processRuns[runId] ?? []), event],
      }
    },
    []
  )

  const resetActiveRunState = useCallback((runtime: SessionChatRuntime) => {
    runtime.streamingContent = ''
    runtime.streamingContentValue = ''
    runtime.pendingToolCalls = []
    runtime.currentToolCalls = []
    runtime.currentRunId = null
    runtime.currentRunIdValue = null
    runtime.isLoading = false
  }, [])

  const persistRunTimelineMessage = useCallback((runtime: SessionChatRuntime, runId: string) => {
    runtime.messages = [
      ...runtime.messages,
      {
        id: generateId(),
        role: 'assistant',
        content: '',
        metadata: { runId },
        createdAt: new Date().toISOString(),
      },
    ]
  }, [])

  const finalizeFailedRun = useCallback(
    (streamKey: string, errorMessage: string, timestamp?: string) => {
      const runtime = getRuntime(streamKey)
      const runId = runtime.currentRunIdValue
      if (runId) {
        appendProcessEvent(runtime, runId, {
          id: generateId(),
          kind: 'error',
          timestamp: timestamp ?? new Date().toISOString(),
          payload: { error: errorMessage },
        })
        persistRunTimelineMessage(runtime, runId)
      }
      resetActiveRunState(runtime)
      if (streamKey === viewKeyRef.current) {
        syncViewToReact()
      }
    },
    [
      appendProcessEvent,
      getRuntime,
      persistRunTimelineMessage,
      resetActiveRunState,
      syncViewToReact,
    ]
  )

  const handleEvent = useCallback(
    (event: ChatEvent) => {
      const streamKey = streamKeyRef.current
      const runtime = getRuntime(streamKey)
      const streamSessionId = streamKey === DRAFT_SESSION_KEY ? sessionIdRef.current : streamKey

      const maybeSyncView = (): void => {
        if (streamKey === viewKeyRef.current) {
          syncViewToReact()
        }
      }

      switch (event.type) {
        case 'session_created': {
          const sessionData = event.data as { session_id?: string }
          if (sessionData.session_id) {
            const newId = sessionData.session_id
            if (streamKey === DRAFT_SESSION_KEY) {
              migrateRuntimeKey(DRAFT_SESSION_KEY, newId)
            }
            sessionIdRef.current = newId
            markStreamActive(newId)
            startTransition(() => {
              void queryClient.invalidateQueries({ queryKey: ['sessions'] })
            })
            onSessionCreatedRef.current?.(newId)
            useChatStore.getState().clearPendingMCPConfig()
            syncViewToReact()
          }
          break
        }

        case 'session_recreated': {
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

          if (sessionRecreationInfo.isRecreated && sessionRecreationInfo.previousState) {
            runtime.sessionRecreation = sessionRecreationInfo
            maybeSyncView()
          }
          break
        }

        case 'title_updated': {
          const titleData = event.data as { session_id?: string; title?: string }
          if (titleData.session_id) {
            void queryClient.invalidateQueries({ queryKey: ['sessions'] })
            if (sessionIdRef.current === titleData.session_id && titleData.title) {
              void queryClient.invalidateQueries({ queryKey: ['session', titleData.session_id] })
            }
          }
          break
        }

        case 'thinking': {
          if (runtime.currentRunIdValue) {
            appendProcessEvent(runtime, runtime.currentRunIdValue, {
              id: generateId(),
              kind: 'thinking',
              timestamp: event.timestamp,
              payload: event.data,
            })
            maybeSyncView()
          }
          break
        }

        case 'text': {
          const textData = event.data as { content?: string }
          if (textData.content) {
            runtime.streamingContentValue += textData.content
            runtime.streamingContent = runtime.streamingContentValue
            if (runtime.currentRunIdValue) {
              appendProcessEvent(runtime, runtime.currentRunIdValue, {
                id: generateId(),
                kind: 'text',
                timestamp: event.timestamp,
                payload: textData,
              })
            }
            maybeSyncView()
          }
          break
        }

        case 'tool_call': {
          const toolCallData = event.data as {
            tool_call_id?: string
            tool_name?: string
            arguments?: Record<string, unknown>
          }
          const toolCall: ToolCall = {
            id: toolCallData.tool_call_id ?? generateId(),
            name: toolCallData.tool_name ?? 'unknown',
            arguments: toolCallData.arguments ?? {},
          }
          runtime.currentToolCalls.push(toolCall)
          runtime.pendingToolCalls = [...runtime.currentToolCalls]
          if (runtime.currentRunIdValue) {
            appendProcessEvent(runtime, runtime.currentRunIdValue, {
              id: generateId(),
              kind: 'tool_call',
              timestamp: event.timestamp,
              payload: event.data,
            })
          }
          maybeSyncView()
          break
        }

        case 'tool_result': {
          const resultData = event.data as { tool_call_id?: string; toolCallId?: string }
          const toolCallId = resultData.tool_call_id ?? resultData.toolCallId
          runtime.currentToolCalls = runtime.currentToolCalls.filter((tc) => tc.id !== toolCallId)
          runtime.pendingToolCalls = [...runtime.currentToolCalls]
          if (runtime.currentRunIdValue) {
            appendProcessEvent(runtime, runtime.currentRunIdValue, {
              id: generateId(),
              kind: 'tool_result',
              timestamp: event.timestamp,
              payload: event.data,
            })
          }
          maybeSyncView()
          break
        }

        case 'interrupt': {
          const interruptData = event.data as unknown as InterruptState
          runtime.interrupt = interruptData
          runtime.isLoading = false
          if (runtime.currentRunIdValue) {
            appendProcessEvent(runtime, runtime.currentRunIdValue, {
              id: generateId(),
              kind: 'interrupt',
              timestamp: event.timestamp,
              payload: event.data,
            })
          }
          maybeSyncView()
          break
        }

        case 'done': {
          const doneData = event.data as {
            final_message?: { content?: string; reasoning_content?: string }
            total_tokens?: number
            usage?: Record<string, unknown>
            model?: string
          }
          const doneContent = doneData.final_message?.content?.trim() ?? ''
          const finalContent =
            doneContent.length > 0 ? doneContent : runtime.streamingContentValue.trim()
          const runId = runtime.currentRunIdValue
          const metadata: Record<string, unknown> = runId ? { runId } : {}
          if (doneData.usage) metadata.usage = doneData.usage
          if (doneData.model) metadata.model = doneData.model
          if (typeof doneData.total_tokens === 'number') {
            metadata.totalTokens = doneData.total_tokens
          }

          if (finalContent) {
            runtime.messages = [
              ...runtime.messages,
              {
                id: generateId(),
                role: 'assistant',
                content: finalContent,
                metadata: Object.keys(metadata).length > 0 ? metadata : undefined,
                tokenCount:
                  typeof doneData.total_tokens === 'number' ? doneData.total_tokens : undefined,
                createdAt: new Date().toISOString(),
              },
            ]
          }

          if (runId) {
            appendProcessEvent(runtime, runId, {
              id: generateId(),
              kind: 'done',
              timestamp: event.timestamp,
              payload: event.data,
            })
          }

          resetActiveRunState(runtime)
          abortMapRef.current.delete(streamKey)
          finishStream(streamSessionId)
          maybeSyncView()

          if (streamSessionId) {
            setTimeout(() => {
              startTransition(() => {
                void queryClient.invalidateQueries({ queryKey: ['sessions'] })
              })
            }, 1000)
          }
          break
        }

        case 'error': {
          const errorData = event.data as { error: string }
          onErrorRef.current?.(new Error(errorData.error))
          finalizeFailedRun(streamKey, errorData.error, event.timestamp)
          abortMapRef.current.delete(streamKey)
          finishStream(streamSessionId)
          break
        }

        case 'terminated': {
          runtime.isLoading = false
          abortMapRef.current.delete(streamKey)
          finishStream(streamSessionId)
          maybeSyncView()
          break
        }
      }
    },
    [
      appendProcessEvent,
      finalizeFailedRun,
      finishStream,
      getRuntime,
      markStreamActive,
      migrateRuntimeKey,
      queryClient,
      resetActiveRunState,
      syncViewToReact,
    ]
  )

  const cancelRequest = useCallback(() => {
    const viewKey = viewKeyRef.current
    const abort = abortMapRef.current.get(viewKey)
    if (abort) {
      abort.abort()
      abortMapRef.current.delete(viewKey)
    }
    const runtime = getRuntime(viewKey)
    resetActiveRunState(runtime)
    syncViewToReact()
    const endedSessionId = viewKey === DRAFT_SESSION_KEY ? undefined : viewKey
    finishStream(endedSessionId)
  }, [finishStream, getRuntime, resetActiveRunState, syncViewToReact])

  const sendMessage = useCallback(
    async (
      content: string,
      options?: {
        modelRef?: string | null
        gatewayTeamId?: string
        gatewayVerboseRequestLog?: boolean
        creativeMode?: 'chat' | 'image_gen'
        referenceImageUrls?: string[]
        imageGenStrength?: number | null
      }
    ) => {
      const viewKey = viewKeyRef.current
      const runtime = getRuntime(viewKey)
      if (!content.trim() || runtime.isLoading) return

      const prevAbort = abortMapRef.current.get(viewKey)
      if (prevAbort) {
        prevAbort.abort()
        abortMapRef.current.delete(viewKey)
      }

      const abortController = new AbortController()
      abortMapRef.current.set(viewKey, abortController)

      const userMessage: Message = {
        id: generateId(),
        role: 'user',
        content: content.trim(),
        createdAt: new Date().toISOString(),
      }
      runtime.messages = [...runtime.messages, userMessage]
      runtime.isLoading = true
      runtime.streamingContent = ''
      runtime.streamingContentValue = ''
      runtime.interrupt = null
      runtime.currentToolCalls = []
      runtime.pendingToolCalls = []

      const runId = generateId()
      runtime.currentRunId = runId
      runtime.currentRunIdValue = runId
      runtime.processRuns = { ...runtime.processRuns, [runId]: [] }

      streamKeyRef.current = viewKey
      markStreamActive(sessionIdRef.current)
      syncViewToReact()

      try {
        const { pendingMCPConfig } = useChatStore.getState()
        const isFirstMessage = !sessionIdRef.current
        const mcpConfig =
          isFirstMessage && pendingMCPConfig.length > 0
            ? { enabledServers: pendingMCPConfig }
            : undefined

        await chatApi.sendMessage(
          {
            message: content,
            sessionId: sessionIdRef.current,
            agentId,
            mcpConfig,
            modelRef: options?.modelRef === undefined ? undefined : options.modelRef,
            gatewayTeamId: options?.gatewayTeamId,
            gatewayVerboseRequestLog: options?.gatewayVerboseRequestLog ?? undefined,
            creativeMode: options?.creativeMode,
            referenceImageUrls: options?.referenceImageUrls,
            imageGenStrength: options?.imageGenStrength,
          },
          handleEvent,
          (error) => {
            if (error.name !== 'AbortError') {
              onErrorRef.current?.(error)
              finalizeFailedRun(viewKey, error.message)
            } else {
              resetActiveRunState(runtime)
              if (viewKey === viewKeyRef.current) syncViewToReact()
            }
            abortMapRef.current.delete(viewKey)
            finishStream(sessionIdRef.current)
          },
          () => {
            resetActiveRunState(runtime)
            abortMapRef.current.delete(viewKey)
            if (viewKey === viewKeyRef.current) syncViewToReact()
            finishStream(sessionIdRef.current)
          },
          abortController.signal
        )
      } catch (error) {
        if ((error as Error).name !== 'AbortError') {
          onErrorRef.current?.(error as Error)
          finalizeFailedRun(viewKey, (error as Error).message)
        } else {
          resetActiveRunState(runtime)
          if (viewKey === viewKeyRef.current) syncViewToReact()
        }
        abortMapRef.current.delete(viewKey)
        finishStream(sessionIdRef.current)
      }
    },
    [
      agentId,
      finalizeFailedRun,
      finishStream,
      getRuntime,
      handleEvent,
      markStreamActive,
      resetActiveRunState,
      syncViewToReact,
    ]
  )

  const resumeExecution = useCallback(
    async (action: 'approve' | 'reject' | 'modify', modifiedArgs?: Record<string, unknown>) => {
      const viewKey = viewKeyRef.current
      const runtime = getRuntime(viewKey)
      const interruptState = runtime.interrupt
      if (!interruptState || !sessionIdRef.current) return

      runtime.isLoading = true
      runtime.interrupt = null
      streamKeyRef.current = viewKey
      syncViewToReact()

      try {
        await chatApi.resume(
          sessionIdRef.current,
          {
            checkpointId: interruptState.checkpointId,
            action,
            modifiedArgs,
          },
          handleEvent,
          (error) => {
            onErrorRef.current?.(error)
            runtime.isLoading = false
            syncViewToReact()
          },
          () => {
            runtime.isLoading = false
            syncViewToReact()
          }
        )
      } catch (error) {
        onErrorRef.current?.(error as Error)
        runtime.isLoading = false
        syncViewToReact()
      }
    },
    [getRuntime, handleEvent, syncViewToReact]
  )

  const clearMessages = useCallback(() => {
    const viewKey = viewKeyRef.current
    runtimeMapRef.current.set(viewKey, createEmptyRuntime())
    syncViewToReact()
  }, [syncViewToReact])

  const switchViewSession = useCallback(
    (sessionId: string | undefined) => {
      const nextKey = toSessionKey(sessionId)
      viewKeyRef.current = nextKey
      sessionIdRef.current = sessionId
      syncViewToReact()
    },
    [syncViewToReact]
  )

  const resetDraftChat = useCallback(() => {
    const draftAbort = abortMapRef.current.get(DRAFT_SESSION_KEY)
    if (draftAbort) {
      draftAbort.abort()
      abortMapRef.current.delete(DRAFT_SESSION_KEY)
    }
    runtimeMapRef.current.set(DRAFT_SESSION_KEY, createEmptyRuntime())
    if (viewKeyRef.current === DRAFT_SESSION_KEY) {
      syncViewToReact()
    }
  }, [syncViewToReact])

  const loadMessages = useCallback(
    (loadedMessages: Message[]) => {
      const viewKey = viewKeyRef.current
      const runtime = getRuntime(viewKey)
      const isStreaming = abortMapRef.current.has(viewKey) && runtime.isLoading
      if (!isStreaming) {
        if (loadedMessages.length > runtime.messages.length || runtime.messages.length === 0) {
          runtime.messages = loadedMessages
        }
        runtime.streamingContent = ''
        runtime.streamingContentValue = ''
        runtime.pendingToolCalls = []
        runtime.currentToolCalls = []
        runtime.interrupt = null
        runtime.currentRunId = null
        runtime.currentRunIdValue = null
      }
      syncViewToReact()
    },
    [getRuntime, syncViewToReact]
  )

  const dismissSessionRecreation = useCallback(() => {
    const runtime = getRuntime(viewKeyRef.current)
    runtime.sessionRecreation = null
    syncViewToReact()
  }, [getRuntime, syncViewToReact])

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
    switchViewSession,
    resetDraftChat,
    dismissSessionRecreation,
  }
}
