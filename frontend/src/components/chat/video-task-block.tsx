/**
 * VideoTaskBlock - 聊天流内视频任务块
 *
 * 在 ProcessPanel 中当工具结果为 amazon_video_submit / amazon_video_poll 且含 task_id 时，
 * 用此组件展示紧凑任务卡片（轮询状态、缩略图、跳转详情）。
 */

import { useQuery } from '@tanstack/react-query'
import { Clock, CheckCircle2, XCircle, AlertTriangle, Play, ExternalLink } from 'lucide-react'

import { videoTaskApi } from '@/api/videoTask'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { VideoTaskStatus } from '@/types/video-task'

interface VideoTaskBlockProps {
  taskId: string
  sessionId?: string
}

export function VideoTaskBlock({
  taskId,
  sessionId,
}: Readonly<VideoTaskBlockProps>): React.JSX.Element {
  const {
    data: task,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ['video-task', taskId],
    queryFn: () => videoTaskApi.get(taskId),
    refetchInterval: (query) => {
      const t = query.state.data
      if (t?.status === 'pending' || t?.status === 'running') return 2000
      return false
    },
  })

  if (isLoading || !task) {
    return (
      <div className="flex items-center gap-2 rounded-md border border-border/40 bg-muted/10 px-2.5 py-2">
        <Clock className="h-3.5 w-3.5 animate-pulse text-blue-500" />
        <span className="text-xs text-muted-foreground">加载视频任务…</span>
      </div>
    )
  }

  if (isError) {
    return (
      <div className="flex items-center gap-2 rounded-md border border-red-500/30 bg-red-500/5 px-2.5 py-2">
        <AlertTriangle className="h-3.5 w-3.5 text-red-500" />
        <span className="text-xs text-red-600">获取任务失败</span>
      </div>
    )
  }

  const isProcessing = task.status === 'pending' || task.status === 'running'
  const hasVideo = task.status === 'completed' && !!task.videoUrl
  const href = sessionId
    ? `/video-tasks?sessionId=${encodeURIComponent(sessionId)}`
    : '/video-tasks'

  return (
    <div
      className={cn(
        'overflow-hidden rounded-md border bg-card',
        isProcessing && 'border-blue-500/20'
      )}
    >
      {/* 缩略图或占位 */}
      {hasVideo ? (
        <div className="relative aspect-video w-full bg-black/5">
          <video
            src={task.videoUrl}
            className="h-full w-full object-cover"
            preload="metadata"
            muted
            playsInline
          />
          <div className="absolute inset-0 flex items-center justify-center bg-black/20 opacity-0 transition-opacity hover:opacity-100">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-white/90 shadow">
              <Play className="ml-0.5 h-5 w-5 text-foreground" />
            </div>
          </div>
        </div>
      ) : (
        <div className="flex aspect-video items-center justify-center bg-muted/20">
          {isProcessing ? (
            <Clock className="h-8 w-8 animate-pulse text-blue-500/60" />
          ) : task.status === 'failed' ? (
            <XCircle className="h-8 w-8 text-red-500/60" />
          ) : (
            <CheckCircle2 className="h-8 w-8 text-muted-foreground/40" />
          )}
        </div>
      )}

      <div className="flex items-center justify-between gap-2 border-t border-border/30 px-2.5 py-2">
        <StatusLabel status={task.status} />
        <Button variant="ghost" size="sm" className="h-7 text-xs" asChild>
          <a href={href}>
            <ExternalLink className="mr-1 h-3 w-3" />
            视频任务
          </a>
        </Button>
      </div>
    </div>
  )
}

function StatusLabel({ status }: { status: VideoTaskStatus }): React.JSX.Element {
  const config: Record<VideoTaskStatus, { color: string; label: string }> = {
    pending: { color: 'text-yellow-600', label: '等待中' },
    running: { color: 'text-blue-600', label: '生成中' },
    completed: { color: 'text-green-600', label: '已完成' },
    failed: { color: 'text-red-600', label: '失败' },
    cancelled: { color: 'text-muted-foreground', label: '已取消' },
  }
  const { color, label } = config[status]
  return <span className={cn('text-xs font-medium', color)}>{label}</span>
}
