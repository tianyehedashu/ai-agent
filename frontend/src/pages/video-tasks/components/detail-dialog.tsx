import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import {
  X,
  Play,
  Clock,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Copy,
  ExternalLink,
  Image as ImageIcon,
  RotateCw,
  StopCircle,
  Download,
  Loader2,
} from 'lucide-react'

import { videoTaskApi } from '@/api/videoTask'
import { Button } from '@/components/ui/button'
import { VIDEO_TASK_MARKETPLACES } from '@/constants/video-task'
import { useToast } from '@/hooks/use-toast'
import { cn } from '@/lib/utils'
import type { VideoGenTask, VideoTaskStatus } from '@/types/video-task'

interface VideoTaskDetailDialogProps {
  /** 初始任务数据（用于快速显示，会被实时数据覆盖） */
  task: VideoGenTask | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

/**
 * 任务详情弹窗 - 乔布斯美学
 *
 * 设计理念：
 * - 全屏沉浸式，专注内容本身
 * - 优雅的层次结构，信息递进
 * - 精致的微交互
 * - 大量留白，呼吸感
 */
export default function VideoTaskDetailDialog({
  task: initialTask,
  open,
  onOpenChange,
}: VideoTaskDetailDialogProps): React.JSX.Element {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  // 实时获取最新任务数据
  const { data: liveTask, isLoading } = useQuery({
    queryKey: ['video-task', initialTask?.id],
    queryFn: () => (initialTask ? videoTaskApi.get(initialTask.id) : Promise.reject()),
    enabled: open && !!initialTask,
    // 进行中的任务自动轮询
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (status === 'pending' || status === 'running') {
        return 5000 // 5秒轮询
      }
      return false
    },
    // 使用初始数据快速显示
    initialData: initialTask ?? undefined,
  })

  // 使用实时数据，降级到初始数据
  const task = liveTask ?? initialTask

  const pollMutation = useMutation({
    mutationFn: () => (task ? videoTaskApi.poll(task.id, true) : Promise.resolve(null)),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['video-task', task?.id] })
      void queryClient.invalidateQueries({ queryKey: ['video-tasks'] })
      toast({ title: '已刷新' })
    },
    onError: (error) => {
      toast({
        variant: 'destructive',
        title: '刷新失败',
        description: error instanceof Error ? error.message : '未知错误',
      })
    },
  })

  const submitMutation = useMutation({
    mutationFn: () => (task ? videoTaskApi.submit(task.id) : Promise.resolve(null)),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['video-task', task?.id] })
      void queryClient.invalidateQueries({ queryKey: ['video-tasks'] })
      toast({ title: '已开始生成' })
    },
    onError: (error) => {
      toast({
        variant: 'destructive',
        title: '提交失败',
        description: error instanceof Error ? error.message : '未知错误',
      })
    },
  })

  const cancelMutation = useMutation({
    mutationFn: () => (task ? videoTaskApi.cancel(task.id) : Promise.resolve(null)),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['video-task', task?.id] })
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

  const retryMutation = useMutation({
    mutationFn: () => (task ? videoTaskApi.retry(task.id) : Promise.resolve(null)),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['video-task', task?.id] })
      void queryClient.invalidateQueries({ queryKey: ['video-tasks'] })
      toast({ title: '已开始重新生成' })
    },
    onError: (error) => {
      toast({
        variant: 'destructive',
        title: '重试失败',
        description: error instanceof Error ? error.message : '未知错误',
      })
    },
  })

  const copyToClipboard = (text: string): void => {
    void navigator.clipboard.writeText(text)
    toast({ title: '已复制' })
  }

  return (
    <AnimatePresence>
      {open && task && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-xl"
          onClick={() => { onOpenChange(false); }}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            transition={{ duration: 0.3, ease: [0.23, 1, 0.32, 1] }}
            className="relative mx-4 max-h-[85vh] w-full max-w-2xl overflow-hidden rounded-3xl border border-border/30 bg-card shadow-2xl"
            onClick={(e) => { e.stopPropagation(); }}
          >
            {/* 关闭按钮 */}
            <button
              type="button"
              onClick={() => { onOpenChange(false); }}
              aria-label="关闭"
              className="absolute right-4 top-4 z-10 flex h-8 w-8 items-center justify-center rounded-full bg-muted/50 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              <X className="h-4 w-4" />
            </button>

            {/* 加载状态指示器（实时同步中） */}
            {isLoading && (
              <div className="absolute left-4 top-4 z-10 flex items-center gap-2 rounded-full bg-muted/50 px-3 py-1.5 text-xs text-muted-foreground">
                <Loader2 className="h-3 w-3 animate-spin" />
                同步中
              </div>
            )}

            <div className="max-h-[85vh] overflow-y-auto">
              {/* 头部区域 */}
              <div className="px-8 pb-6 pt-8">
                {/* 完成状态：视频优先展示 */}
                {task.status === 'completed' && task.videoUrl ? (
                  <>
                    {/* 视频播放器 - 最显眼位置 */}
                    <div className="mb-6 overflow-hidden rounded-2xl border border-border/30 bg-black">
                      <video
                        src={task.videoUrl}
                        controls
                        autoPlay
                        className="h-auto w-full max-h-[50vh]"
                        preload="auto"
                        playsInline
                      >
                        您的浏览器不支持视频播放
                      </video>
                    </div>

                    {/* 状态标题 */}
                    <div className="mb-4 text-center">
                      <h2 className="mb-1 text-lg font-medium text-foreground">创作完成</h2>
                      <p className="text-sm text-muted-foreground">
                        {VIDEO_TASK_MARKETPLACES.find((m) => m.value === task.marketplace)?.label ?? task.marketplace}
                      </p>
                    </div>

                    {/* 操作按钮 */}
                    <div className="flex flex-wrap justify-center gap-2">
                      <Button variant="outline" size="sm" className="gap-2" asChild>
                        <a
                          href={task.videoUrl}
                          download
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          <Download className="h-4 w-4" />
                          下载
                        </a>
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="gap-2"
                        onClick={() => { copyToClipboard(task.videoUrl ?? ''); }}
                      >
                        <Copy className="h-4 w-4" />
                        复制链接
                      </Button>
                      <Button variant="ghost" size="sm" className="gap-2" asChild>
                        <a href={task.videoUrl} target="_blank" rel="noopener noreferrer">
                          <ExternalLink className="h-4 w-4" />
                          新窗口
                        </a>
                      </Button>
                    </div>
                  </>
                ) : task.status === 'completed' && !task.videoUrl ? (
                  /* 完成但视频还没准备好 */
                  <>
                    <div className="mb-6 flex justify-center">
                      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-green-500/10 to-green-500/5">
                        <motion.div
                          animate={{ scale: [1, 1.1, 1] }}
                          transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
                        >
                          <CheckCircle2 className="h-7 w-7 text-green-500" />
                        </motion.div>
                      </div>
                    </div>

                    <div className="mb-6 text-center">
                      <h2 className="mb-1 text-xl font-medium text-foreground">视频处理中</h2>
                      <p className="text-sm text-muted-foreground">
                        创作已完成，正在准备视频文件...
                      </p>
                    </div>

                    <div className="flex justify-center">
                      <Button
                        variant="outline"
                        onClick={() => void pollMutation.mutateAsync()}
                        disabled={pollMutation.isPending}
                        className="gap-2 rounded-full"
                      >
                        <RotateCw className={cn('h-4 w-4', pollMutation.isPending && 'animate-spin')} />
                        刷新状态
                      </Button>
                    </div>
                  </>
                ) : (
                  <>
                    {/* 其他状态：显示状态图标 */}
                    <div className="mb-6 flex justify-center">
                      <StatusIcon status={task.status} />
                    </div>

                    {/* 状态标题 */}
                    <div className="mb-6 text-center">
                      <h2 className="mb-1 text-xl font-medium text-foreground">
                        <StatusTitle status={task.status} />
                      </h2>
                      <p className="text-sm text-muted-foreground">
                        {VIDEO_TASK_MARKETPLACES.find((m) => m.value === task.marketplace)?.label ?? task.marketplace}
                      </p>
                    </div>

                    {/* 主要操作 */}
                    <div className="flex justify-center gap-3">
                      {task.status === 'pending' && (
                        <Button
                          onClick={() => void submitMutation.mutateAsync()}
                          disabled={submitMutation.isPending}
                          className="gap-2 rounded-full px-6"
                        >
                          <Play className="h-4 w-4" />
                          开始生成
                        </Button>
                      )}
                      {task.status === 'running' && (
                        <>
                          <Button
                            variant="outline"
                            onClick={() => void pollMutation.mutateAsync()}
                            disabled={pollMutation.isPending}
                            className="gap-2 rounded-full"
                          >
                            <RotateCw className={cn('h-4 w-4', pollMutation.isPending && 'animate-spin')} />
                            刷新
                          </Button>
                          <Button
                            variant="outline"
                            onClick={() => void cancelMutation.mutateAsync()}
                            disabled={cancelMutation.isPending}
                            className="gap-2 rounded-full text-destructive hover:text-destructive"
                          >
                            <StopCircle className="h-4 w-4" />
                            停止
                          </Button>
                        </>
                      )}
                      {task.status === 'pending' && (
                        <Button
                          variant="outline"
                          onClick={() => void cancelMutation.mutateAsync()}
                          disabled={cancelMutation.isPending}
                          className="gap-2 rounded-full"
                        >
                          <XCircle className="h-4 w-4" />
                          取消
                        </Button>
                      )}
                      {(task.status === 'failed' || task.status === 'cancelled') && (
                        <Button
                          onClick={() => void retryMutation.mutateAsync()}
                          disabled={retryMutation.isPending}
                          className="gap-2 rounded-full px-6"
                        >
                          <RotateCw className={cn('h-4 w-4', retryMutation.isPending && 'animate-spin')} />
                          重试
                        </Button>
                      )}
                    </div>
                  </>
                )}
              </div>

              {/* 内容区域 */}
              <div className="space-y-6 border-t border-border/30 px-8 py-6">
                {/* 错误信息 */}
                {task.status === 'failed' && task.errorMessage && (
                  <div className="rounded-2xl bg-destructive/5 p-4">
                    <p className="text-sm text-destructive">{task.errorMessage}</p>
                  </div>
                )}

                {/* 提示词 */}
                <Section title="创作描述">
                  <div className="rounded-2xl bg-muted/30 p-4">
                    <p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground/80">
                      {task.promptText || '暂无描述'}
                    </p>
                  </div>
                </Section>

                {/* 参考图片 */}
                {task.referenceImages.length > 0 && (
                  <Section title="参考图片">
                    <div className="flex flex-wrap gap-2">
                      {task.referenceImages.map((url, i) => (
                        <a
                          key={i}
                          href={url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1.5 rounded-full bg-muted/50 px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                        >
                          <ImageIcon className="h-3 w-3" />
                          图片 {i + 1}
                        </a>
                      ))}
                    </div>
                  </Section>
                )}

                {/* 技术信息（可折叠） */}
                <details className="group">
                  <summary className="flex cursor-pointer items-center gap-2 text-xs text-muted-foreground/60 hover:text-muted-foreground">
                    <span>技术信息</span>
                    <span className="transition-transform group-open:rotate-90">→</span>
                  </summary>
                  <div className="mt-4 space-y-3 rounded-2xl bg-muted/20 p-4 text-xs">
                    <InfoRow label="任务 ID" value={task.id} copyable onCopy={copyToClipboard} />
                    {task.workflowId && (
                      <InfoRow label="Workflow ID" value={task.workflowId} copyable onCopy={copyToClipboard} />
                    )}
                    {task.runId && (
                      <InfoRow label="Run ID" value={task.runId} copyable onCopy={copyToClipboard} />
                    )}
                    <InfoRow 
                      label="提示词来源" 
                      value={formatPromptSource(task.promptSource)} 
                    />
                    <InfoRow
                      label="创建时间"
                      value={new Date(task.createdAt).toLocaleString('zh-CN')}
                    />
                    <InfoRow
                      label="更新时间"
                      value={new Date(task.updatedAt).toLocaleString('zh-CN')}
                    />
                    
                    {/* 复制全部按钮 */}
                    <div className="pt-2 border-t border-border/30">
                      <button
                        type="button"
                        onClick={() => {
                          const info = [
                            `任务 ID: ${task.id}`,
                            task.workflowId ? `Workflow ID: ${task.workflowId}` : null,
                            task.runId ? `Run ID: ${task.runId}` : null,
                            `提示词来源: ${formatPromptSource(task.promptSource)}`,
                            `创建时间: ${new Date(task.createdAt).toLocaleString('zh-CN')}`,
                            `更新时间: ${new Date(task.updatedAt).toLocaleString('zh-CN')}`,
                          ].filter(Boolean).join('\n')
                          copyToClipboard(info)
                        }}
                        className="flex items-center gap-1.5 text-muted-foreground/70 hover:text-muted-foreground transition-colors"
                      >
                        <Copy className="h-3 w-3" />
                        复制全部
                      </button>
                    </div>
                  </div>
                </details>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

/** 状态图标 */
function StatusIcon({ status }: { status: VideoTaskStatus }): React.JSX.Element {
  const baseClass = 'flex h-16 w-16 items-center justify-center rounded-2xl'

  if (status === 'pending' || status === 'running') {
    return (
      <div className={cn(baseClass, 'bg-gradient-to-br from-blue-500/10 to-blue-500/5')}>
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 3, repeat: Infinity, ease: 'linear' }}
        >
          <Clock className="h-7 w-7 text-blue-500" />
        </motion.div>
      </div>
    )
  }

  if (status === 'completed') {
    return (
      <div className={cn(baseClass, 'bg-gradient-to-br from-green-500/10 to-green-500/5')}>
        <CheckCircle2 className="h-7 w-7 text-green-500" />
      </div>
    )
  }

  if (status === 'failed') {
    return (
      <div className={cn(baseClass, 'bg-gradient-to-br from-red-500/10 to-red-500/5')}>
        <AlertTriangle className="h-7 w-7 text-red-500" />
      </div>
    )
  }

  return (
    <div className={cn(baseClass, 'bg-gradient-to-br from-muted/50 to-muted/30')}>
      <XCircle className="h-7 w-7 text-muted-foreground" />
    </div>
  )
}

/** 状态标题 */
function StatusTitle({ status }: { status: VideoTaskStatus }): string {
  switch (status) {
    case 'pending':
      return '等待开始'
    case 'running':
      return '正在创作'
    case 'completed':
      return '创作完成'
    case 'failed':
      return '创作失败'
    case 'cancelled':
      return '已取消'
    default:
      return ''
  }
}

/** 内容分区 */
function Section({
  title,
  children,
}: {
  title: string
  children: React.ReactNode
}): React.JSX.Element {
  return (
    <div>
      <h3 className="mb-3 text-xs font-medium uppercase tracking-wider text-muted-foreground/70">
        {title}
      </h3>
      {children}
    </div>
  )
}

/** 信息行 */
function InfoRow({
  label,
  value,
  copyable,
  onCopy,
}: {
  label: string
  value: string
  copyable?: boolean
  onCopy?: (text: string) => void
}): React.JSX.Element {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="text-muted-foreground">{label}</span>
      <div className="flex items-center gap-1.5">
        <code className="max-w-[200px] truncate text-foreground/70">{value}</code>
        {copyable && onCopy && (
          <button
            type="button"
            onClick={() => { onCopy(value); }}
            aria-label={`复制 ${label}`}
            className="rounded p-1 text-muted-foreground/50 hover:bg-muted hover:text-muted-foreground"
          >
            <Copy className="h-3 w-3" />
          </button>
        )}
      </div>
    </div>
  )
}

/** 格式化提示词来源 */
function formatPromptSource(source: string | undefined): string {
  const sourceMap: Record<string, string> = {
    user_provided: '用户输入',
    agent_generated: 'AI 生成',
    template: '模板',
  }
  return source ? (sourceMap[source] ?? source) : '-'
}
