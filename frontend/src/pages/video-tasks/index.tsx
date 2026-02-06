import { useState, useEffect, useRef, useCallback } from 'react'

import { useQuery, useQueryClient } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import { Clock, Sparkles } from 'lucide-react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { videoTaskApi } from '@/api/videoTask'
import { cn } from '@/lib/utils'
import type { VideoGenTask } from '@/types/video-task'

import VideoTaskCreateForm from './components/create-form'
import VideoTaskDetailDialog from './components/detail-dialog'
import TaskTimelineCard from './components/task-timeline-card'

/** 示例提示 - 简短、有吸引力 */
const examplePrompts = [
  { short: '咖啡机', full: '一款精致的咖啡机，展示研磨咖啡豆、萃取浓缩咖啡的全过程' },
  { short: '智能手表', full: '智能手表在手腕上，展示表盘切换、心率监测、消息提醒功能' },
  { short: '无线耳机', full: '无线耳机从充电盒中取出，佩戴入耳，展示触控操作和降噪效果' },
  { short: '护肤精华', full: '护肤精华液滴落在手背，轻柔涂抹，展示吸收过程和肌肤光泽' },
]

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
  const [selectedTask, setSelectedTask] = useState<VideoGenTask | null>(null)
  const [selectedExample, setSelectedExample] = useState<string | null>(null)
  const scrollContainerRef = useRef<HTMLDivElement>(null)
  const queryClient = useQueryClient()

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

    return () => { clearInterval(pollInterval); }
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
        // 刷新当前会话的任务列表
        void queryClient.invalidateQueries({
          queryKey: ['video-tasks', 'session', sessionId],
        })
      }

      // 清空选中的示例
      setSelectedExample(null)

      // 自动滚动到顶部（最新任务）
      setTimeout(() => {
        scrollContainerRef.current?.scrollTo({
          top: 0,
          behavior: 'smooth',
        })
      }, 100)
    },
    [queryClient, sessionId, navigate]
  )

  // 点击示例填充输入框
  const handleExampleClick = (prompt: string): void => {
    setSelectedExample(prompt)
  }

  const hasRecentTasks = recentTasks.length > 0

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

      {/* 任务列表区 - 可滚动 */}
      <div
        ref={scrollContainerRef}
        className="flex-1 overflow-y-auto px-4 py-6 sm:px-6"
      >
        <AnimatePresence mode="wait">
          {!hasRecentTasks ? (
            /* 欢迎状态 - 无任务时显示 */
            <WelcomeState
              key="welcome"
              onExampleClick={handleExampleClick}
              selectedExample={selectedExample}
            />
          ) : (
            /* 任务时间线 */
            <motion.div
              key="timeline"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="mx-auto max-w-2xl space-y-4 pb-4 pt-12"
            >
              {recentTasks.map((task) => (
                <TaskTimelineCard
                  key={task.id}
                  task={task}
                  onClick={() => { setSelectedTask(task); }}
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
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* 输入框 - 固定底部 */}
      <div className="flex-none border-t border-border/30 bg-background/95 px-4 py-4 backdrop-blur-xl sm:px-6">
        <div className="mx-auto max-w-2xl">
          {/* 示例提示 - 仅在有任务时显示在输入框上方 */}
          {hasRecentTasks && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="mb-3 flex items-center justify-center gap-2"
            >
              <span className="text-xs text-muted-foreground/50">试试：</span>
              <div className="flex flex-wrap justify-center gap-1.5">
                {examplePrompts.map((prompt, i) => (
                  <button
                    key={i}
                    onClick={() => { handleExampleClick(prompt.full); }}
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
        <p className="text-base text-muted-foreground/80">
          描述你的想象，AI 将其转化为视频
        </p>
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
            {examplePrompts.map((prompt, i) => (
              <button
                key={i}
                onClick={() => { onExampleClick(prompt.full); }}
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
