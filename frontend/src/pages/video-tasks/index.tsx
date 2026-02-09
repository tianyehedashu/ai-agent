import { useState, useEffect, useRef, useCallback } from 'react'

import { useQuery, useQueryClient } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import { Clock, Sparkles } from 'lucide-react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { sessionApi } from '@/api/session'
import { videoTaskApi } from '@/api/videoTask'
import { VIDEO_TASK_EXAMPLE_PROMPTS } from '@/constants/video-task'
import { InterruptDialog } from '@/components/chat/interrupt-dialog'
import { useChat } from '@/hooks/use-chat'
import { useToast } from '@/hooks/use-toast'
import { cn } from '@/lib/utils'
import ChatMessages from '@/pages/chat/components/chat-messages'
import { useChatStore } from '@/stores/chat'
import type { VideoGenTask } from '@/types/video-task'

import VideoTaskCreateForm from './components/create-form'
import VideoTaskDetailDialog from './components/detail-dialog'
import TaskTimelineCard from './components/task-timeline-card'

/**
 * 视频生成页面 - 聊天流布局
 *
 * 设计哲学：
 * - 聊天流：连续创作，历史可见
 * - 极简：去除干扰，聚焦创作
 * - 留白：大量负空间让内容呼吸
 * - 情感：细腻的动效传递温度
 */
export default function VideoTasksPage(): React.JSX.Element {
  const { sessionId } = useParams<{ sessionId?: string }>()
  const navigate = useNavigate()
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const { setCurrentSession } = useChatStore()

  const [selectedTask, setSelectedTask] = useState<VideoGenTask | null>(null)
  const [selectedExample, setSelectedExample] = useState<string | null>(null)
  const scrollContainerRef = useRef<HTMLDivElement>(null)
  const prevSessionIdRef = useRef<string | undefined>(undefined)

  // 集成 useChat hook - 获取消息状态和发送功能
  const {
    messages,
    isLoading: isChatLoading,
    streamingContent,
    pendingToolCalls,
    interrupt,
    processRuns,
    currentRunId,
    resumeExecution,
    clearMessages,
    loadMessages,
  } = useChat({
    sessionId,
    onError: (error) => {
      toast({
        title: '错误',
        description: error.message,
        variant: 'destructive',
      })
    },
    onSessionCreated: (id) => {
      navigate(`/video-tasks/${id}`)
    },
  })

  // 获取任务列表（仅在有 sessionId 时加载，无 sessionId 为新建页面）
  const { data: tasksData } = useQuery({
    queryKey: ['video-tasks', 'session', sessionId],
    queryFn: () => videoTaskApi.list({ sessionId, limit: 50 }),
    enabled: !!sessionId,
    refetchInterval: 30000, // 30秒刷新
  })

  const recentTasks = tasksData?.items ?? []

  // 筛选进行中的任务
  const runningTasks = recentTasks.filter(
    (t) =>
      t.status === 'pending' ||
      t.status === 'running' ||
      (t.status === 'completed' && !t.videoUrl)
  )

  // 加载会话信息和历史消息
  useEffect(() => {
    const prevSessionId = prevSessionIdRef.current
    prevSessionIdRef.current = sessionId

    // 切换会话时清除消息
    const isLeavingOrSwitching =
      prevSessionId !== undefined && (sessionId === undefined || prevSessionId !== sessionId)
    if (isLeavingOrSwitching) {
      clearMessages()
    }

    let cancelled = false

    if (sessionId) {
      // 加载会话信息
      sessionApi
        .get(sessionId)
        .then((session) => {
          if (!cancelled) {
            setCurrentSession(session)
          }
        })
        .catch((error: unknown) => {
          if (!cancelled) {
            console.error('Failed to load session:', error)
          }
        })

      // 加载历史消息
      sessionApi
        .getMessages(sessionId)
        .then((msgs) => {
          if (!cancelled) {
            loadMessages(msgs)
          }
        })
        .catch((error: unknown) => {
          if (!cancelled) {
            console.error('Failed to load messages:', error)
          }
        })
    } else {
      setCurrentSession(null)
    }

    return () => {
      cancelled = true
    }
  }, [sessionId, setCurrentSession, clearMessages, loadMessages])

  // 轮询进行中的任务（仅在有 sessionId 时）
  useEffect(() => {
    if (!sessionId || runningTasks.length === 0) return

    const pollInterval = setInterval(() => {
      runningTasks.forEach((task) => {
        void videoTaskApi.poll(task.id, true).then(() => {
          void queryClient.invalidateQueries({ queryKey: ['video-tasks', 'session', sessionId] })
        })
      })
    }, 5000) // 5秒轮询

    return () => {
      clearInterval(pollInterval)
    }
  }, [sessionId, runningTasks, queryClient])

  // 任务创建后的处理
  const handleTaskCreated = useCallback(
    (newTask: VideoGenTask): void => {
      // 如果当前没有 sessionId 但新任务有，导航到该会话的视频页面
      if (!sessionId && newTask.sessionId) {
        navigate(`/video-tasks/${newTask.sessionId}`)
        // 刷新 sessions 列表（侧栏显示新会话）
        void queryClient.invalidateQueries({ queryKey: ['sessions'] })
      } else if (sessionId) {
        // 刷新当前会话的任务列表和消息
        void queryClient.invalidateQueries({
          queryKey: ['video-tasks', 'session', sessionId],
        })
        // 重新加载消息（因为后端会保存用户消息）
        sessionApi.getMessages(sessionId).then(loadMessages).catch(console.error)
      }

      // 清空选中的示例
      setSelectedExample(null)

      // 自动滚动到底部（最新内容）
      setTimeout(() => {
        scrollContainerRef.current?.scrollTo({
          top: scrollContainerRef.current.scrollHeight,
          behavior: 'smooth',
        })
      }, 100)
    },
    [queryClient, sessionId, navigate, loadMessages]
  )

  // 点击示例填充输入框
  const handleExampleClick = (prompt: string): void => {
    setSelectedExample(prompt)
  }

  const hasContent = messages.length > 0 || recentTasks.length > 0

  return (
    <div className="relative flex h-[calc(100vh-3.5rem)] flex-col">
      {/* 顶部导航栏 - 极简 */}
      <header className="absolute right-4 top-4 z-10 sm:right-6">
        <Link
          to="/video-tasks/history"
          className="group inline-flex items-center gap-2 rounded-full bg-background/60 px-4 py-2 text-sm text-muted-foreground backdrop-blur-sm transition-all hover:bg-background/80 hover:text-foreground"
        >
          <Clock className="h-4 w-4 transition-transform group-hover:-rotate-12" />
          <span>历史</span>
        </Link>
      </header>

      {/* 内容区 - 消息和任务混合显示 */}
      <div ref={scrollContainerRef} className="flex-1 overflow-y-auto">
        <AnimatePresence mode="wait">
          {!hasContent ? (
            /* 欢迎状态 - 无内容时显示 */
            <WelcomeState
              key="welcome"
              onExampleClick={handleExampleClick}
              selectedExample={selectedExample}
            />
          ) : (
            /* 聊天消息和任务卡片 */
            <motion.div
              key="content"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex flex-col"
            >
              {/* 消息历史区域 */}
              {messages.length > 0 && (
                <div className="flex-1">
                  <ChatMessages
                    messages={messages}
                    streamingContent={streamingContent}
                    isLoading={isChatLoading}
                    pendingToolCalls={pendingToolCalls}
                    processRuns={processRuns}
                    currentRunId={currentRunId}
                  />
                </div>
              )}

              {/* 视频任务卡片区域 */}
              {recentTasks.length > 0 && (
                <div className="mx-auto w-full max-w-3xl space-y-4 px-4 py-6">
                  <div className="mb-2 text-xs text-muted-foreground/60">视频任务</div>
                  {recentTasks.map((task) => (
                    <TaskTimelineCard
                      key={task.id}
                      task={task}
                      onClick={() => {
                        setSelectedTask(task)
                      }}
                    />
                  ))}

                  {/* 加载更多提示 */}
                  <div className="flex justify-center py-4">
                    <Link
                      to="/video-tasks/history"
                      className="text-xs text-muted-foreground/50 transition-colors hover:text-muted-foreground"
                    >
                      查看更多历史 →
                    </Link>
                  </div>
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* 输入框 - 固定底部 */}
      <div className="flex-none border-t border-border/30 bg-background/95 px-4 py-4 backdrop-blur-xl sm:px-6">
        <div className="mx-auto max-w-2xl">
          {/* 示例提示 - 仅在有内容时显示在输入框上方 */}
          {hasContent && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="mb-3 flex items-center justify-center gap-2"
            >
              <span className="text-xs text-muted-foreground/50">试试：</span>
              <div className="flex flex-wrap justify-center gap-1.5">
                {VIDEO_TASK_EXAMPLE_PROMPTS.map((prompt, i) => (
                  <button
                    key={i}
                    onClick={() => {
                      handleExampleClick(prompt.full)
                    }}
                    className={cn(
                      'rounded-full px-3 py-1 text-xs transition-all duration-200',
                      selectedExample === prompt.full
                        ? 'bg-primary/10 text-primary'
                        : 'text-muted-foreground/60 hover:text-muted-foreground'
                    )}
                  >
                    {prompt.short}
                  </button>
                ))}
              </div>
            </motion.div>
          )}

          <VideoTaskCreateForm
            onTaskCreated={handleTaskCreated}
            onSessionForbidden={() => navigate('/video-tasks')}
            disabled={false}
            initialPrompt={selectedExample ?? undefined}
            sessionId={sessionId}
          />
        </div>
      </div>

      {/* 详情弹窗 */}
      <VideoTaskDetailDialog
        task={selectedTask}
        open={!!selectedTask}
        onOpenChange={(open) => {
          if (!open) setSelectedTask(null)
        }}
      />

      {/* HITL 中断对话框 */}
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

/**
 * 欢迎状态 - 无任务时的引导界面
 */
function WelcomeState({
  onExampleClick,
  selectedExample,
}: {
  onExampleClick: (prompt: string) => void
  selectedExample: string | null
}): React.JSX.Element {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.5, ease: [0.23, 1, 0.32, 1] }}
      className="flex min-h-full flex-col items-center justify-center py-16"
    >
      {/* 图标 */}
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ delay: 0.1, duration: 0.5 }}
        className="mb-8"
      >
        <div className="flex h-20 w-20 items-center justify-center rounded-3xl bg-gradient-to-br from-primary/10 to-primary/5">
          <Sparkles className="h-10 w-10 text-primary/60" />
        </div>
      </motion.div>

      {/* 标题区 */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2, duration: 0.6, ease: [0.23, 1, 0.32, 1] }}
        className="mb-12 text-center"
      >
        <h1 className="mb-3 text-3xl font-semibold tracking-tight text-foreground">
          创造视觉故事
        </h1>
        <p className="text-base text-muted-foreground/80">描述你的想象，AI 将其转化为视频</p>
      </motion.div>

      {/* 示例提示 */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.5, duration: 0.5 }}
      >
        <div className="flex flex-col items-center gap-3">
          <span className="text-xs text-muted-foreground/50">或者试试这些：</span>
          <div className="flex flex-wrap justify-center gap-2">
            {VIDEO_TASK_EXAMPLE_PROMPTS.map((prompt, i) => (
              <button
                key={i}
                onClick={() => {
                  onExampleClick(prompt.full)
                }}
                className={cn(
                  'rounded-full border px-4 py-2 text-sm transition-all duration-200',
                  selectedExample === prompt.full
                    ? 'border-primary/30 bg-primary/10 text-primary'
                    : 'border-border/50 text-muted-foreground hover:border-border hover:text-foreground'
                )}
              >
                {prompt.short}
              </button>
            ))}
          </div>
        </div>
      </motion.div>
    </motion.div>
  )
}
