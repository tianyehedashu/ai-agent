import { useState, useEffect } from 'react'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ArrowLeft,
  Play,
  Clock,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  MoreHorizontal,
  Trash2,
  ExternalLink,
  Sparkles,
  Download,
} from 'lucide-react'
import { Link } from 'react-router-dom'

import { videoTaskApi } from '@/api/videoTask'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { VIDEO_TASK_MARKETPLACE_FLAGS } from '@/constants/video-task'
import { useToast } from '@/hooks/use-toast'
import { cn } from '@/lib/utils'
import type { VideoGenTask, VideoTaskStatus } from '@/types/video-task'

import VideoTaskDetailDialog from './components/detail-dialog'

const statusFilters = [
  { value: 'all', label: '全部' },
  { value: 'pending', label: '待提交' },
  { value: 'running', label: '进行中' },
  { value: 'completed', label: '已完成' },
  { value: 'failed', label: '失败' },
  { value: 'cancelled', label: '已取消' },
]

/**
 * 历史任务页面 - 乔布斯美学
 *
 * 设计理念：
 * - 画廊式布局，每个作品都是艺术品
 * - 简约的筛选，不打扰浏览
 * - 优雅的悬浮交互
 * - 大量留白，呼吸感
 */
export default function VideoTasksHistoryPage(): React.JSX.Element {
  const [selectedTask, setSelectedTask] = useState<VideoGenTask | null>(null)
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [displayLimit, setDisplayLimit] = useState(12)
  const queryClient = useQueryClient()
  const { toast } = useToast()

  // 切换筛选时重置分页
  useEffect(() => { setDisplayLimit(12) }, [statusFilter])

  const { data: tasksData, isLoading } = useQuery({
    queryKey: ['video-tasks', 'history', statusFilter, displayLimit],
    queryFn: () =>
      videoTaskApi.list({
        limit: displayLimit,
        status: statusFilter === 'all' ? undefined : (statusFilter as VideoTaskStatus),
      }),
    refetchInterval: 30000,
  })

  const tasks = tasksData?.items ?? []
  const runningTasks = tasks.filter((t) => t.status === 'running')

  useEffect(() => {
    if (runningTasks.length === 0) return
    const pollInterval = setInterval(() => {
      runningTasks.forEach((task) => {
        void videoTaskApi.poll(task.id, true).then(() => {
          void queryClient.invalidateQueries({ queryKey: ['video-tasks'] })
        })
      })
    }, 15000)
    return () => { clearInterval(pollInterval); }
  }, [runningTasks, queryClient])

  const cancelMutation = useMutation({
    mutationFn: (id: string) => videoTaskApi.cancel(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['video-tasks'] })
      toast({ title: '已取消' })
    },
    onError: (error) => {
      toast({
        variant: 'destructive',
        title: '取消失败',
        description: error instanceof Error ? error.message : '未知错误',
      })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => videoTaskApi.delete(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['video-tasks'] })
      toast({ title: '已删除' })
    },
    onError: (error) => {
      toast({
        variant: 'destructive',
        title: '删除失败',
        description: error instanceof Error ? error.message : '未知错误',
      })
    },
  })

  const submitMutation = useMutation({
    mutationFn: (id: string) => videoTaskApi.submit(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['video-tasks'] })
      toast({ title: '已开始' })
    },
    onError: (error) => {
      toast({
        variant: 'destructive',
        title: '提交失败',
        description: error instanceof Error ? error.message : '未知错误',
      })
    },
  })

  return (
    <div className="min-h-screen">
      {/* 顶部导航 - 极简固定 */}
      <header className="sticky top-0 z-20 border-b border-border/30 bg-background/80 backdrop-blur-xl">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-6">
          <Link
            to="/video-tasks"
            className="group inline-flex items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeft className="h-4 w-4 transition-transform group-hover:-translate-x-1" />
            <span>返回</span>
          </Link>

          {/* 筛选标签 - 药丸式设计 */}
          <div className="flex items-center gap-1 rounded-full bg-muted/50 p-1">
            {statusFilters.map((filter) => (
              <button
                key={filter.value}
                onClick={() => { setStatusFilter(filter.value); }}
                className={cn(
                  'rounded-full px-4 py-1.5 text-sm transition-all duration-200',
                  statusFilter === filter.value
                    ? 'bg-background text-foreground shadow-sm'
                    : 'text-muted-foreground hover:text-foreground'
                )}
              >
                {filter.label}
              </button>
            ))}
          </div>

          <div className="w-16" /> {/* 平衡布局 */}
        </div>
      </header>

      {/* 内容区 */}
      <main className="mx-auto max-w-6xl px-6 py-8">
        <AnimatePresence mode="wait">
          {isLoading ? (
            <LoadingState key="loading" />
          ) : tasks.length === 0 ? (
            <EmptyState key="empty" statusFilter={statusFilter} />
          ) : (
            <motion.div
              key="content"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {tasks.map((task, index) => (
                  <motion.div
                    key={task.id}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: index * 0.05, duration: 0.3 }}
                  >
                    <TaskCard
                      task={task}
                      onView={() => { setSelectedTask(task); }}
                      onSubmit={() => void submitMutation.mutateAsync(task.id)}
                      onCancel={() => void cancelMutation.mutateAsync(task.id)}
                      onDelete={() => {
                        if (confirm('确定要删除这个任务吗？')) {
                          void deleteMutation.mutateAsync(task.id)
                        }
                      }}
                    />
                  </motion.div>
                ))}
              </div>
              {tasks.length < (tasksData?.total ?? 0) && (
                <div className="flex justify-center py-8">
                  <button
                    onClick={() => { setDisplayLimit((l) => l + 12); }}
                    className="text-sm text-muted-foreground/60 transition-colors hover:text-foreground"
                  >
                    加载更多
                  </button>
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </main>

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

/** 加载状态 - 优雅的骨架屏 */
function LoadingState(): React.JSX.Element {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
    >
      {[1, 2, 3, 4, 5, 6].map((i) => (
        <div
          key={i}
          className="animate-pulse rounded-2xl border border-border/30 bg-card p-5"
        >
          <div className="mb-4 h-4 w-2/3 rounded-full bg-muted" />
          <div className="mb-2 h-3 w-full rounded-full bg-muted/60" />
          <div className="h-3 w-4/5 rounded-full bg-muted/40" />
        </div>
      ))}
    </motion.div>
  )
}

/** 空状态 - 温暖的引导 */
function EmptyState({ statusFilter }: { statusFilter: string }): React.JSX.Element {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      className="flex min-h-[50vh] flex-col items-center justify-center text-center"
    >
      <div className="mb-6 flex h-20 w-20 items-center justify-center rounded-3xl bg-gradient-to-br from-muted/50 to-muted/30">
        <Sparkles className="h-10 w-10 text-muted-foreground/50" />
      </div>
      <h2 className="mb-2 text-lg font-medium text-foreground">
        {statusFilter === 'all' ? '还没有创作' : '没有匹配的任务'}
      </h2>
      <p className="mb-6 max-w-xs text-sm text-muted-foreground">
        {statusFilter === 'all'
          ? '开始你的第一个视频创作吧'
          : '试试切换其他筛选条件'}
      </p>
      {statusFilter === 'all' && (
        <Button asChild className="rounded-full px-6">
          <Link to="/video-tasks">开始创作</Link>
        </Button>
      )}
    </motion.div>
  )
}

/** 任务卡片 - 精致的悬浮交互 */
function TaskCard({
  task,
  onView,
  onSubmit,
  onCancel,
  onDelete,
}: Readonly<{
  task: VideoGenTask
  onView: () => void
  onSubmit: () => void
  onCancel: () => void
  onDelete: () => void
}>): React.JSX.Element {
  const isProcessing = task.status === 'pending' || task.status === 'running'
  const flag = VIDEO_TASK_MARKETPLACE_FLAGS[task.marketplace] ?? '🌐'

  return (
    <div
      onClick={onView}
      className={cn(
        'group relative cursor-pointer rounded-2xl border bg-card p-5 transition-all duration-300',
        'hover:border-border hover:shadow-lg hover:shadow-primary/5',
        'border-border/30'
      )}
    >
      {/* 头部：状态 + 操作 */}
      <div className="mb-4 flex items-start justify-between">
        <StatusBadge status={task.status} />
        <DropdownMenu>
          <DropdownMenuTrigger asChild onClick={(e) => { e.stopPropagation(); }}>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 rounded-full opacity-0 transition-opacity group-hover:opacity-100"
            >
              <MoreHorizontal className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="min-w-[140px]" onClick={(e) => { e.stopPropagation(); }}>
            {task.status === 'pending' && (
              <DropdownMenuItem onClick={onSubmit}>
                <Play className="mr-2 h-4 w-4" />
                开始生成
              </DropdownMenuItem>
            )}
            {task.status === 'completed' && task.videoUrl && (
              <>
                <DropdownMenuItem onClick={onView}>
                  <Play className="mr-2 h-4 w-4" />
                  播放
                </DropdownMenuItem>
                <DropdownMenuItem asChild>
                  <a href={task.videoUrl} download target="_blank" rel="noopener noreferrer">
                    <Download className="mr-2 h-4 w-4" />
                    下载
                  </a>
                </DropdownMenuItem>
                <DropdownMenuItem asChild>
                  <a href={task.videoUrl} target="_blank" rel="noopener noreferrer">
                    <ExternalLink className="mr-2 h-4 w-4" />
                    新窗口打开
                  </a>
                </DropdownMenuItem>
              </>
            )}
            {isProcessing && (
              <DropdownMenuItem onClick={onCancel}>
                <XCircle className="mr-2 h-4 w-4" />
                取消
              </DropdownMenuItem>
            )}
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={onDelete} className="text-destructive focus:text-destructive">
              <Trash2 className="mr-2 h-4 w-4" />
              删除
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {/* 内容预览 */}
      <p className="mb-4 line-clamp-2 min-h-[40px] text-sm leading-relaxed text-foreground/80">
        {task.promptText || '暂无描述'}
      </p>

      {/* 底部：时间 + 站点 */}
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>{formatRelativeTime(task.createdAt)}</span>
        <span>{flag}</span>
      </div>

      {/* 进行中的脉动效果 */}
      {isProcessing && (
        <div className="absolute inset-0 -z-10 animate-pulse rounded-2xl bg-primary/5" />
      )}
    </div>
  )
}

/** 状态徽章 - 简约的圆点设计 */
function StatusBadge({ status }: { status: VideoTaskStatus }): React.JSX.Element {
  const config: Record<VideoTaskStatus, { color: string; icon: React.ElementType; label: string }> = {
    pending: { color: 'bg-yellow-500', icon: Clock, label: '等待中' },
    running: { color: 'bg-blue-500', icon: Clock, label: '生成中' },
    completed: { color: 'bg-green-500', icon: CheckCircle2, label: '已完成' },
    failed: { color: 'bg-red-500', icon: AlertTriangle, label: '失败' },
    cancelled: { color: 'bg-gray-400', icon: XCircle, label: '已取消' },
  }

  const { color, label } = config[status]
  const isAnimating = status === 'pending' || status === 'running'

  return (
    <div className="flex items-center gap-2">
      <span className="relative flex h-2 w-2">
        {isAnimating && (
          <span className={cn('absolute inline-flex h-full w-full animate-ping rounded-full opacity-75', color)} />
        )}
        <span className={cn('relative inline-flex h-2 w-2 rounded-full', color)} />
      </span>
      <span className="text-xs text-muted-foreground">{label}</span>
    </div>
  )
}

/** 相对时间格式化 */
function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMins < 1) return '刚刚'
  if (diffMins < 60) return `${diffMins} 分钟前`
  if (diffHours < 24) return `${diffHours} 小时前`
  if (diffDays < 7) return `${diffDays} 天前`
  return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}
