import { motion } from 'framer-motion'
import { Clock, CheckCircle2, XCircle, AlertTriangle, Play, Sparkles, RotateCw } from 'lucide-react'

import { VIDEO_TASK_MARKETPLACE_FLAGS } from '@/constants/video-task'
import { cn } from '@/lib/utils'
import type { VideoGenTask, VideoTaskStatus } from '@/types/video-task'

interface TaskTimelineCardProps {
  task: VideoGenTask
  onClick: () => void
}

/**
 * 任务时间线卡片 - 乔布斯美学
 *
 * 设计理念：
 * - 极简：只展示最核心的信息
 * - 呼吸：充足的留白和圆角
 * - 聚焦：视频缩略图是视觉焦点
 * - 温度：细腻的动效传递情感
 */
export default function TaskTimelineCard({
  task,
  onClick,
}: TaskTimelineCardProps): React.JSX.Element {
  const isProcessing = task.status === 'pending' || task.status === 'running'
  const hasVideo = task.status === 'completed' && !!task.videoUrl
  const flag = VIDEO_TASK_MARKETPLACE_FLAGS[task.marketplace] ?? '🌐'

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.23, 1, 0.32, 1] }}
      onClick={onClick}
      className={cn(
        'group relative cursor-pointer rounded-2xl border bg-card transition-all duration-300',
        'hover:border-border hover:shadow-lg hover:shadow-primary/5',
        'border-border/30',
        isProcessing && 'border-blue-500/20'
      )}
    >
      {/* 视频缩略图区域 */}
      {hasVideo && (
        <div className="relative aspect-video w-full overflow-hidden rounded-t-2xl bg-black/5">
          <video
            src={task.videoUrl}
            className="h-full w-full object-cover"
            preload="metadata"
            muted
            playsInline
          />
          {/* 播放按钮遮罩 */}
          <div className="absolute inset-0 flex items-center justify-center bg-black/20 opacity-0 transition-opacity duration-300 group-hover:opacity-100">
            <div className="flex h-14 w-14 items-center justify-center rounded-full bg-white/90 shadow-lg backdrop-blur-sm transition-transform duration-300 group-hover:scale-110">
              <Play className="ml-1 h-6 w-6 text-foreground" />
            </div>
          </div>
        </div>
      )}

      {/* 进行中状态：加载动画 */}
      {isProcessing && (
        <div className="relative aspect-video w-full overflow-hidden rounded-t-2xl bg-gradient-to-br from-blue-500/5 to-blue-500/10">
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 3, repeat: Infinity, ease: 'linear' }}
              className="mb-3"
            >
              <Clock className="h-10 w-10 text-blue-500/60" />
            </motion.div>
            <span className="text-sm text-blue-500/80">
              {task.status === 'pending' ? '准备中...' : '创作中...'}
            </span>
          </div>
          {/* 脉动效果 */}
          <motion.div
            className="absolute inset-0 bg-blue-500/5"
            animate={{ opacity: [0.3, 0.6, 0.3] }}
            transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
          />
        </div>
      )}

      {/* 完成但视频还没准备好 */}
      {task.status === 'completed' && !task.videoUrl && (
        <div className="relative aspect-video w-full overflow-hidden rounded-t-2xl bg-gradient-to-br from-green-500/5 to-green-500/10">
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <motion.div
              animate={{ scale: [1, 1.1, 1] }}
              transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
              className="mb-3"
            >
              <CheckCircle2 className="h-10 w-10 text-green-500/60" />
            </motion.div>
            <span className="text-sm text-green-500/80">视频处理中...</span>
            <span className="mt-1 text-xs text-muted-foreground/60">请稍候，正在准备视频</span>
          </div>
        </div>
      )}

      {/* 失败/取消状态 */}
      {(task.status === 'failed' || task.status === 'cancelled') && (
        <div className="relative aspect-video w-full overflow-hidden rounded-t-2xl bg-gradient-to-br from-muted/30 to-muted/50">
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            {task.status === 'failed' ? (
              <>
                <AlertTriangle className="mb-2 h-10 w-10 text-red-500/60" />
                <span className="text-sm text-red-500/80">创作失败</span>
              </>
            ) : (
              <>
                <XCircle className="mb-2 h-10 w-10 text-muted-foreground/40" />
                <span className="text-sm text-muted-foreground/60">已取消</span>
              </>
            )}
          </div>
          {/* 重试提示遮罩 */}
          <div className="absolute inset-0 flex items-center justify-center bg-black/20 opacity-0 transition-opacity duration-300 group-hover:opacity-100">
            <div className="flex h-14 w-14 items-center justify-center rounded-full bg-white/90 shadow-lg backdrop-blur-sm transition-transform duration-300 group-hover:scale-110">
              <RotateCw className="h-6 w-6 text-foreground" />
            </div>
          </div>
        </div>
      )}

      {/* 内容区域 */}
      <div className="p-4">
        {/* 状态 + 元信息行 */}
        <div className="mb-2 flex items-center justify-between">
          <StatusBadge status={task.status} />
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span className="flex items-center gap-1">
              <Sparkles className="h-3 w-3" />
              {task.model.split('::')[1] ?? task.model}
            </span>
            <span>{flag}</span>
          </div>
        </div>

        {/* 提示词文本 */}
        <p className="mb-2 line-clamp-2 text-sm leading-relaxed text-foreground/80">
          {task.promptText !== undefined && task.promptText !== '' ? task.promptText : '暂无描述'}
        </p>

        {/* 错误信息 */}
        {task.status === 'failed' && task.errorMessage && (
          <p className="mb-2 line-clamp-1 text-xs text-red-500/70">{task.errorMessage}</p>
        )}

        {/* 时间 */}
        <div className="text-xs text-muted-foreground/60">{formatRelativeTime(task.createdAt)}</div>
      </div>

      {/* 进行中的边框动画 */}
      {isProcessing && (
        <div className="pointer-events-none absolute inset-0 rounded-2xl">
          <div className="absolute inset-0 animate-pulse rounded-2xl border-2 border-blue-500/20" />
        </div>
      )}
    </motion.div>
  )
}

/** 状态徽章 - 简约的圆点设计 */
function StatusBadge({ status }: { status: VideoTaskStatus }): React.JSX.Element {
  const config: Record<VideoTaskStatus, { color: string; label: string }> = {
    pending: { color: 'bg-yellow-500', label: '等待中' },
    running: { color: 'bg-blue-500', label: '生成中' },
    completed: { color: 'bg-green-500', label: '已完成' },
    failed: { color: 'bg-red-500', label: '失败' },
    cancelled: { color: 'bg-gray-400', label: '已取消' },
  }

  const { color, label } = config[status]
  const isAnimating = status === 'pending' || status === 'running'

  return (
    <div className="flex items-center gap-2">
      <span className="relative flex h-2 w-2">
        {isAnimating && (
          <span
            className={cn(
              'absolute inline-flex h-full w-full animate-ping rounded-full opacity-75',
              color
            )}
          />
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
  if (diffMins < 60) return `${String(diffMins)} 分钟前`
  if (diffHours < 24) return `${String(diffHours)} 小时前`
  if (diffDays < 7) return `${String(diffDays)} 天前`
  return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}
