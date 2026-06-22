import { useEffect, useRef, useState, useCallback, useMemo } from 'react'

import { useQuery, useQueryClient } from '@tanstack/react-query'
import { History, Wrench } from 'lucide-react'
import { useParams, useNavigate } from 'react-router-dom'

import { gatewayApi } from '@/api/gateway'
import { sessionApi } from '@/api/session'
import { videoTaskApi } from '@/api/videoTask'
import { InterruptDialog } from '@/components/chat/interrupt-dialog'
import { SessionNotice } from '@/components/chat/session-notice'
import { TimeTravelDebugger } from '@/components/chat/time-travel-debugger'
import { ModelSelector } from '@/components/model-selector'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { useChat } from '@/hooks/use-chat'
import { useGatewayWorkspaceTeamId } from '@/hooks/use-gateway-team-id'
import { useToast } from '@/hooks/use-toast'
import { useChatStore } from '@/stores/chat'
import type { SessionCreativeMode } from '@/types'

import { ChatGatewaySetupAlert, isChatReady } from './components/chat-gateway-setup-alert'
import ChatMessages from './components/chat-messages'
import { MCPSessionConfig } from './components/mcp-session-config'
import ChatSessionVideoTasks from './components/session-video-tasks'
import UnifiedInputArea, {
  type CreativeInputMode,
  type VideoCreateParams,
} from './components/unified-input-area'

export default function ChatPage(): React.JSX.Element {
  const { sessionId } = useParams<{ sessionId?: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [showDebugger, setShowDebugger] = useState(false)
  const [creativeMode, setCreativeMode] = useState<CreativeInputMode>('chat')
  const { setCurrentSession, input, setInput, newChatEpoch } = useChatStore()
  const [toolConfigOpen, setToolConfigOpen] = useState(false)
  const [selectedModelRef, setSelectedModelRef] = useState<string | null>(null)
  const [selectedImageGenModelRef, setSelectedImageGenModelRef] = useState<string | null>(null)
  const [referenceImageUrls, setReferenceImageUrls] = useState('')
  /** 网关调用详细日志：无会话时仅作用于下一条发送；有会话时切换会 PATCH 持久化到会话 */
  const [verboseGatewayLog, setVerboseGatewayLog] = useState(false)
  const workspaceTeamId = useGatewayWorkspaceTeamId()

  const prevSessionIdRef = useRef<string | undefined>(undefined)
  /** 流式创建会话后 navigate 到 /chat/:id 时跳过拉历史，避免覆盖进行中的 SSE 内容 */
  const skipHistoryLoadForSessionRef = useRef<string | null>(null)
  /** 进行中的 SSE 流所属 sessionId 集合（与 useChat 同步） */
  const activeStreamSessionsRef = useRef<Set<string>>(new Set())

  const handleChatError = useCallback(
    (error: Error) => {
      toast({
        title: '错误',
        description: error.message,
        variant: 'destructive',
      })
    },
    [toast]
  )

  const handleSessionCreated = useCallback(
    (id: string) => {
      skipHistoryLoadForSessionRef.current = id
      navigate(`/chat/${id}`, { replace: true })
    },
    [navigate]
  )

  const handleStreamEnd = useCallback((endedSessionId: string | undefined) => {
    if (endedSessionId && skipHistoryLoadForSessionRef.current === endedSessionId) {
      skipHistoryLoadForSessionRef.current = null
    }
  }, [])

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
    loadMessages,
    switchViewSession,
    resetDraftChat,
    dismissSessionRecreation,
  } = useChat({
    sessionId,
    activeStreamSessionsRef,
    onStreamEnd: handleStreamEnd,
    onError: handleChatError,
    onSessionCreated: handleSessionCreated,
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

  const {
    data: availableTextModels,
    isPending,
    isFetching,
  } = useQuery({
    queryKey: ['gateway-models-available', 'text', '', '', workspaceTeamId ?? ''],
    queryFn: () =>
      gatewayApi.listAvailableModels('text', undefined, {
        ...(workspaceTeamId ? { gatewayTeamId: workspaceTeamId } : {}),
      }),
    staleTime: 30_000,
    enabled: workspaceTeamId !== null,
  })

  const chatModelsLoaded = availableTextModels !== undefined
  const chatReadiness = availableTextModels?.chat_readiness
  const chatModelsLoading =
    workspaceTeamId !== null && !chatModelsLoaded && (isPending || isFetching)
  const chatModelsReady = isChatReady(chatReadiness)

  const firstSelectablePersonalModelId = useMemo(() => {
    const items = availableTextModels?.user_models.items ?? []
    for (const model of items) {
      if (model.is_active && model.last_test_status !== 'failed') return model.id
    }
    return undefined
  }, [availableTextModels?.user_models.items])

  const resolveChatModelRef = useCallback((): string | undefined => {
    const defaultId = availableTextModels?.default_for_text?.id
    return selectedModelRef ?? defaultId ?? firstSelectablePersonalModelId ?? undefined
  }, [availableTextModels?.default_for_text?.id, selectedModelRef, firstSelectablePersonalModelId])

  // 侧栏「新建对话」已在 /chat 时 sessionId 不变，仅重置草稿区（不中断其他会话后台流）
  useEffect(() => {
    if (newChatEpoch === 0) return
    resetDraftChat()
    switchViewSession(undefined)
  }, [newChatEpoch, resetDraftChat, switchViewSession])

  // 无会话时（新建对话）切回对话模式，避免底部只显示 Tab 不显示输入
  useEffect(() => {
    if (!sessionId) setCreativeMode('chat')
  }, [sessionId])

  // Load session - 当 sessionId 变化时，仅「离开当前会话」或「切换到另一会话」时清除消息；
  // 「无会话 → 新会话」时不清空，保留乐观添加的首条消息
  useEffect(() => {
    const prevSessionId = prevSessionIdRef.current
    prevSessionIdRef.current = sessionId

    const isLeavingOrSwitching =
      prevSessionId !== undefined && (sessionId === undefined || prevSessionId !== sessionId)
    if (isLeavingOrSwitching) {
      if (sessionId === undefined) {
        resetDraftChat()
      }
      switchViewSession(sessionId)
    }

    // 使用标志位来跟踪这个 effect 是否仍然有效
    let cancelled = false

    if (sessionId) {
      const skipHistory =
        skipHistoryLoadForSessionRef.current === sessionId ||
        activeStreamSessionsRef.current.has(sessionId)

      const applySession = (session: Awaited<ReturnType<typeof sessionApi.get>>): void => {
        if (cancelled) return
        setCurrentSession(session)
        setSelectedModelRef(session.chatModelRef ?? null)
        setVerboseGatewayLog(session.gatewayVerboseRequestLog ?? false)
        const cm = session.creativeMode
        if (cm === 'image_gen' || cm === 'video') {
          setCreativeMode(cm)
        } else {
          setCreativeMode('chat')
        }
        setSelectedImageGenModelRef(session.imageGenModelRef ?? null)
      }

      if (skipHistory) {
        sessionApi
          .get(sessionId)
          .then(applySession)
          .catch((error: unknown) => {
            if (!cancelled) {
              console.error('Failed to load session:', error)
              handleSessionAccessError(error)
            }
          })
      } else {
        Promise.all([sessionApi.get(sessionId), sessionApi.getMessages(sessionId)])
          .then(([session, messages]) => {
            applySession(session)
            if (!cancelled) {
              loadMessages(messages)
            }
          })
          .catch((error: unknown) => {
            if (!cancelled) {
              console.error('Failed to load session:', error)
              handleSessionAccessError(error)
            }
          })
      }
    } else {
      setCurrentSession(null)
      setSelectedModelRef(null)
      setSelectedImageGenModelRef(null)
      setReferenceImageUrls('')
      setVerboseGatewayLog(false)
    }

    // 清理函数：当 sessionId 变化或组件卸载时调用
    return () => {
      cancelled = true
    }
  }, [
    sessionId,
    setCurrentSession,
    switchViewSession,
    resetDraftChat,
    loadMessages,
    handleSessionAccessError,
  ])

  const handleCreativeModeChange = async (mode: CreativeInputMode): Promise<void> => {
    setCreativeMode(mode)
    if (!sessionId) return
    try {
      const updated = await sessionApi.update(sessionId, {
        creativeMode: mode as SessionCreativeMode,
      })
      setCurrentSession(updated)
    } catch (error: unknown) {
      const msg = error instanceof Error ? error.message : '更新失败'
      toast({
        title: '无法保存创作模式',
        description: msg,
        variant: 'destructive',
      })
    }
  }

  const handleSend = async (): Promise<void> => {
    if (!input.trim() || isLoading) return
    if (creativeMode === 'chat' && !chatModelsReady) {
      toast({
        title: '无法发送',
        description: '请先在 Gateway 完成凭据与对话模型配置。',
        variant: 'destructive',
      })
      return
    }
    const message = input.trim()
    setInput('')
    const refLines = referenceImageUrls
      .split('\n')
      .map((s) => s.trim())
      .filter((u) => u.startsWith('http://') || u.startsWith('https://'))

    if (creativeMode === 'image_gen') {
      const defaultImg = (
        await gatewayApi.listAvailableModels('image_gen', undefined, {
          mode: 'image_gen',
          ...(workspaceTeamId ? { gatewayTeamId: workspaceTeamId } : {}),
        })
      ).default_for_image_gen?.id
      const modelRef = selectedImageGenModelRef ?? defaultImg ?? undefined
      await sendMessage(message, {
        modelRef,
        gatewayTeamId: workspaceTeamId ?? undefined,
        gatewayVerboseRequestLog: verboseGatewayLog ? true : undefined,
        creativeMode: 'image_gen',
        referenceImageUrls: refLines.length > 0 ? refLines : undefined,
      })
      if (sessionId && modelRef) {
        try {
          const updated = await sessionApi.update(sessionId, { imageGenModelRef: modelRef })
          setCurrentSession(updated)
        } catch {
          /* 非阻塞 */
        }
      }
      return
    }

    const modelRef = resolveChatModelRef()
    await sendMessage(message, {
      modelRef,
      gatewayTeamId: workspaceTeamId ?? undefined,
      gatewayVerboseRequestLog: verboseGatewayLog ? true : undefined,
      creativeMode: 'chat',
      referenceImageUrls: refLines.length > 0 ? refLines : undefined,
    })
  }

  const handleVerboseGatewayLogChange = async (checked: boolean): Promise<void> => {
    const previous = verboseGatewayLog
    setVerboseGatewayLog(checked)
    if (!sessionId) return
    try {
      const updated = await sessionApi.update(sessionId, { gatewayVerboseRequestLog: checked })
      setCurrentSession(updated)
    } catch (error: unknown) {
      setVerboseGatewayLog(previous)
      const msg = error instanceof Error ? error.message : '更新失败'
      toast({
        title: '无法更新会话设置',
        description: msg,
        variant: 'destructive',
      })
    }
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
      {/* 右上角：对话工具（始终显示）、时间旅行（仅在有会话时） */}
      <div className="absolute right-4 top-3 z-10 flex gap-2">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            setToolConfigOpen(true)
          }}
          className="h-8 gap-1.5 rounded-full bg-background/80 px-3 text-xs text-muted-foreground shadow-sm backdrop-blur-sm hover:bg-background hover:text-foreground"
          title="配置本对话可用的工具与 MCP 服务器"
        >
          <Wrench className="h-3.5 w-3.5" />
          <span className="hidden sm:inline">对话工具</span>
        </Button>
        {sessionId && (
          <>
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
          </>
        )}
      </div>

      {/* 对话工具与 MCP 配置：有 session 时读写 API，无 session 时读写本地待用配置 */}
      <MCPSessionConfig
        sessionId={sessionId}
        open={toolConfigOpen}
        onOpenChange={setToolConfigOpen}
      />

      {/* Session Recreation Notice */}
      {sessionRecreation && (
        <div className="px-4 pt-4 sm:px-6">
          <div className="mx-auto max-w-3xl">
            <SessionNotice data={sessionRecreation} onDismiss={dismissSessionRecreation} />
          </div>
        </div>
      )}

      {creativeMode === 'chat' && workspaceTeamId !== null ? (
        <div className="px-4 pt-4 sm:px-6">
          <ChatGatewaySetupAlert
            readiness={chatReadiness}
            workspaceTeamId={workspaceTeamId}
            modelsLoaded={chatModelsLoaded}
          />
        </div>
      ) : null}

      {/* Messages Area - Centered with max width */}
      <div className="flex-1 overflow-hidden">
        <ChatMessages
          messages={messages}
          streamingContent={streamingContent}
          isLoading={isLoading}
          pendingToolCalls={pendingToolCalls}
          processRuns={processRuns}
          currentRunId={currentRunId}
          sessionId={sessionId}
          onPromptSelect={setInput}
        />
      </div>

      {/* 本会话视频任务区块 - 仅当有 session 且有任务时显示 */}
      <ChatSessionVideoTasks sessionId={sessionId} />

      {/* Input Area - Fixed at bottom with centered content */}
      <div className="relative z-10 border-t border-border/60 bg-card/70 pb-4 pt-3 shadow-[0_-12px_30px_-24px_hsl(var(--foreground)/0.35)] backdrop-blur-xl supports-[backdrop-filter]:bg-card/60">
        <div className="mx-auto max-w-3xl px-4">
          <UnifiedInputArea
            creativeMode={creativeMode}
            onCreativeModeChange={(m) => {
              void handleCreativeModeChange(m)
            }}
            sessionId={sessionId}
            chatValue={input}
            chatOnChange={setInput}
            chatOnSend={handleSend}
            chatIsLoading={
              isLoading || (creativeMode === 'chat' && (!chatModelsReady || chatModelsLoading))
            }
            referenceImageUrls={referenceImageUrls}
            onReferenceImageUrlsChange={setReferenceImageUrls}
            toolbarLeftExtra={
              creativeMode !== 'video' ? (
                <div className="flex items-center gap-0.5">
                  {creativeMode === 'image_gen' ? (
                    <ModelSelector
                      modelType="image_gen"
                      listMode="image_gen"
                      gatewayTeamId={workspaceTeamId}
                      value={selectedImageGenModelRef}
                      onChange={setSelectedImageGenModelRef}
                      disabled={isLoading}
                      showProviderFilter
                      className="h-8 w-[min(12rem,calc(100vw-10rem))] max-w-[12rem] border-0 bg-transparent shadow-none focus:ring-0"
                    />
                  ) : (
                    <ModelSelector
                      modelType="text"
                      listMode="chat"
                      gatewayTeamId={workspaceTeamId}
                      value={selectedModelRef}
                      onChange={setSelectedModelRef}
                      disabled={isLoading}
                      showProviderFilter
                      className="h-8 w-[min(12rem,calc(100vw-10rem))] max-w-[12rem] border-0 bg-transparent shadow-none focus:ring-0"
                    />
                  )}
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 shrink-0 rounded-lg text-muted-foreground/70 transition-colors hover:bg-secondary hover:text-foreground"
                    title="配置本对话可用的工具与 MCP 服务器"
                    onClick={() => {
                      setToolConfigOpen(true)
                    }}
                  >
                    <Wrench className="h-4 w-4" />
                  </Button>
                  <div className="flex shrink-0 items-center gap-1.5 rounded-lg border border-border/60 bg-muted/20 px-2 py-0.5">
                    <Switch
                      id="verbose-gateway-log"
                      checked={verboseGatewayLog}
                      onCheckedChange={(v) => {
                        void handleVerboseGatewayLogChange(v)
                      }}
                      disabled={isLoading}
                      className="scale-90"
                    />
                    <Label
                      htmlFor="verbose-gateway-log"
                      className="cursor-pointer whitespace-nowrap text-[11px] text-muted-foreground sm:text-xs"
                      title={
                        sessionId
                          ? '开启后本会话内网关调用会记录更长的提示词与模型回复摘要（仍截断落库）。关闭将同步保存到会话。'
                          : '开启后下一条消息将请求扩展网关日志（需服务端允许）；进入已有会话后可用会话级开关持久化。'
                      }
                    >
                      <span className="hidden sm:inline">网关详细日志</span>
                      <span className="sm:hidden">日志</span>
                    </Label>
                  </div>
                </div>
              ) : undefined
            }
            onVideoTaskCreated={() => {
              toast({
                title: '视频任务已创建',
                description: '正在跳转到视频任务页',
              })
              if (sessionId) {
                navigate(`/video-tasks/${sessionId}`)
              }
              void handleCreativeModeChange('chat')
            }}
            onVideoSessionForbidden={() => {
              navigate('/video-tasks')
              void handleCreativeModeChange('chat')
            }}
            onVideoCreateWithoutSession={async (params: VideoCreateParams) => {
              const session = await sessionApi.create()
              await videoTaskApi.create({
                sessionId: session.id,
                promptText: params.promptText,
                promptSource: 'user_provided',
                marketplace: 'jp',
                model: params.model,
                duration: params.duration,
                referenceImages: params.referenceImages,
                autoSubmit: true,
              })
              void queryClient.invalidateQueries({ queryKey: ['sessions'] })
              toast({
                title: '视频任务已创建',
                description: '正在跳转到视频任务页',
              })
              navigate(`/video-tasks/${session.id}`)
              void handleCreativeModeChange('chat')
            }}
          />
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
