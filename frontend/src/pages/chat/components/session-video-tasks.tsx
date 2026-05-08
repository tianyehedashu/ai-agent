/**
 * 本会话视频任务区块 - Phase 2
 *
 * 仅当 sessionId 存在时渲染，展示当前会话的视频任务列表；
 * 进行中任务自动轮询，点击卡片打开详情弹窗。
 */

import { useState } from 'react'

import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { videoTaskApi } from '@/api/videoTask'
import { cn } from '@/lib/utils'
import VideoTaskDetailDialog from '@/pages/video-tasks/components/detail-dialog'
import TaskTimelineCard from '@/pages/video-tasks/components/task-timeline-card'
import type { VideoGenTask } from '@/types/video-task'

interface ChatSessionVideoTasksProps {
  sessionId: string | undefined
  className?: string
}

export default function ChatSessionVideoTasks({
  sessionId,
  className,
}: Readonly<ChatSessionVideoTasksProps>): React.JSX.Element | null {
  const queryClient = useQueryClient()
  const [selectedTask, setSelectedTask] = useState<VideoGenTask | null>(null)

  const { data: tasksData } = useQuery({
    queryKey: ['video-tasks', 'session', sessionId],
    queryFn: () => videoTaskApi.list({ sessionId, limit: 20 }),
    enabled: !!sessionId,
    refetchInterval: (query) => {
      const items = query.state.data?.items ?? []
      const hasRunning = items.some(
        (t) =>
          t.status === 'pending' ||
          t.status === 'running' ||
          (t.status === 'completed' && !t.videoUrl)
      )
      return hasRunning ? 5000 : false
    },
  })

  const tasks = tasksData?.items ?? []

  if (!sessionId || tasks.length === 0) return null

  return (
    <div className={cn('border-t border-border/30 bg-muted/5', className)}>
      <div className="mx-auto max-w-3xl px-4 py-4">
        <div className="mb-3 flex items-center justify-between">
          <span className="text-xs font-medium text-muted-foreground/80">本会话视频任务</span>
          <Link
            to={sessionId ? `/video-tasks/${sessionId}` : '/video-tasks'}
            className="text-xs text-muted-foreground/60 transition-colors hover:text-muted-foreground"
          >
            全部 →
          </Link>
        </div>
        <div className="space-y-3">
          {tasks.map((task) => (
            <TaskTimelineCard
              key={task.id}
              task={task}
              onClick={() => {
                setSelectedTask(task)
              }}
            />
          ))}
        </div>
      </div>

      <VideoTaskDetailDialog
        task={selectedTask}
        open={!!selectedTask}
        onOpenChange={(open) => {
          if (!open) setSelectedTask(null)
          if (!open && selectedTask) {
            void queryClient.invalidateQueries({
              queryKey: ['video-tasks', 'session', sessionId],
            })
          }
        }}
      />
    </div>
  )
}
