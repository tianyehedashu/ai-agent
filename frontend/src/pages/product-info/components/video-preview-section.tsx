/**
 * 视频预览区：等待状态、播放展示、创建入口
 * 整合到产品信息页，无需跳转视频任务页
 *
 * 通过 prompt_source = "product_info::<jobId>" 将视频任务绑定到当前 job，
 * 查询和展示时只显示属于当前 job 的视频。
 */

import { useState, useCallback } from 'react'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Video,
  Loader2,
  AlertTriangle,
  XCircle,
  ChevronDown,
  ChevronUp,
  Sparkles,
  Clock,
} from 'lucide-react'

import { videoTaskApi } from '@/api/videoTask'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Textarea } from '@/components/ui/textarea'
import { VIDEO_MODELS, getVideoDurations } from '@/constants/video-task'
import { useProductInfoCapabilities } from '@/hooks/use-product-info-capabilities'
import { useToast } from '@/hooks/use-toast'
import type { VideoGenTask, VideoModel, VideoDuration } from '@/types/video-task'

function makePromptSource(jobId: string): string {
  return `product_info::${jobId}`
}

interface VideoPreviewSectionProps {
  /** 当前 job ID（用于绑定视频任务） */
  jobId: string | null
  /** 当前 job（用于取视频脚本） */
  currentJob: {
    steps?: Array<{ capability_id: string; output_snapshot?: Record<string, unknown> | null }>
  } | null
  /** 8 图 URL 列表（用于参考图） */
  imageUrls: string[]
}

export function VideoPreviewSection({
  jobId,
  currentJob,
  imageUrls,
}: VideoPreviewSectionProps): React.JSX.Element {
  const caps = useProductInfoCapabilities()
  const [showCreate, setShowCreate] = useState(false)
  const [promptText, setPromptText] = useState('')
  const [model, setModel] = useState<VideoModel>('openai::sora2.0')
  const [duration, setDuration] = useState<VideoDuration>(15)
  const queryClient = useQueryClient()
  const { toast } = useToast()

  const promptSource = jobId ? makePromptSource(jobId) : null

  const stepVideo = currentJob?.steps?.find((s) => s.capability_id === 'video_script')
  const snapshot = stepVideo?.output_snapshot as Record<string, unknown> | undefined
  const videoPrompt = snapshot?.video_prompt
  const outputKey = caps.outputKeys.video_script
  const videoScript = snapshot?.[outputKey]
  const defaultPrompt =
    typeof videoPrompt === 'string' && videoPrompt.trim()
      ? videoPrompt
      : typeof videoScript === 'string'
        ? videoScript
        : ''

  const { data: listData } = useQuery({
    queryKey: ['video-tasks', 'product-info', jobId],
    queryFn: () => {
      if (promptSource === null) {
        throw new Error('prompt source missing')
      }
      return videoTaskApi.list({
        limit: 5,
        promptSource,
      })
    },
    enabled: !!promptSource,
    refetchInterval: (query) => {
      const data = query.state.data as { items?: VideoGenTask[] } | undefined
      const items = data?.items ?? []
      const top = items.at(0)
      if (top?.status === 'pending' || top?.status === 'running') return 5000
      return false
    },
  })
  const tasks = listData?.items ?? []
  const latestTask = tasks.at(0)

  const createMutation = useMutation({
    mutationFn: () => {
      if (promptSource === null) {
        throw new Error('prompt source missing')
      }
      return videoTaskApi.create({
        promptText: promptText.trim() || defaultPrompt || undefined,
        promptSource,
        referenceImages: imageUrls,
        marketplace: 'jp',
        model,
        duration,
        autoSubmit: true,
      })
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['video-tasks', 'product-info', jobId] })
      toast({ title: '已开始生成', description: '视频将在上方展示' })
      setShowCreate(false)
      setPromptText('')
    },
    onError: (err) => {
      toast({ title: '创建失败', description: String(err), variant: 'destructive' })
    },
  })

  const handleCreate = useCallback(() => {
    if (!promptSource) {
      toast({ title: '请先创建任务', variant: 'destructive' })
      return
    }
    if (promptText.trim() || defaultPrompt) {
      createMutation.mutate()
    } else {
      toast({ title: '请填写视频描述', variant: 'destructive' })
    }
  }, [promptText, defaultPrompt, promptSource, createMutation, toast])

  const hasVideo = latestTask?.status === 'completed' && Boolean(latestTask.videoUrl)
  const isProcessing = latestTask?.status === 'pending' || latestTask?.status === 'running'

  return (
    <div className="rounded-xl border border-border/50 bg-card p-5 shadow-sm">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10">
            <Video className="h-4 w-4 text-primary" />
          </div>
          <div>
            <h3 className="text-base font-semibold tracking-tight">视频</h3>
            <p className="text-sm text-muted-foreground">基于本页主图或分析结果生成视频</p>
          </div>
        </div>
      </div>

      {/* 视频展示 / 等待 / 占位 */}
      <div className="relative aspect-video w-full max-w-2xl overflow-hidden rounded-lg border border-border/50 bg-muted/20">
        {hasVideo ? (
          <video
            src={latestTask.videoUrl ?? ''}
            className="h-full w-full object-contain"
            controls
            playsInline
          />
        ) : isProcessing ? (
          <div className="flex h-full flex-col items-center justify-center gap-2">
            <Loader2 className="h-10 w-10 animate-spin text-primary/70" />
            <span className="text-sm text-muted-foreground">
              {latestTask.status === 'pending' ? '等待中…' : '生成中…'}
            </span>
          </div>
        ) : latestTask?.status === 'failed' ? (
          <div className="flex h-full flex-col items-center justify-center gap-2">
            <AlertTriangle className="h-10 w-10 text-destructive/70" />
            <span className="text-sm text-destructive/80">生成失败</span>
            {latestTask.errorMessage ? (
              <span className="max-w-full truncate px-3 text-sm text-muted-foreground">
                {latestTask.errorMessage}
              </span>
            ) : null}
          </div>
        ) : latestTask?.status === 'cancelled' ? (
          <div className="flex h-full flex-col items-center justify-center gap-2">
            <XCircle className="h-10 w-10 text-muted-foreground" />
            <span className="text-sm text-muted-foreground">已取消</span>
          </div>
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-2">
            <Video className="h-10 w-10 text-muted-foreground opacity-50" />
            <span className="text-sm text-muted-foreground">暂无视频</span>
          </div>
        )}
      </div>

      {/* 生成入口 */}
      <div className="mt-3">
        <button
          type="button"
          className="flex w-full items-center justify-between rounded-lg py-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
          onClick={() => {
            setShowCreate((v) => !v)
          }}
        >
          <span>生成视频</span>
          {showCreate ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
        </button>
        {showCreate && (
          <div className="space-y-3 rounded-lg border border-border/50 bg-muted/20 p-4">
            <Textarea
              placeholder={
                defaultPrompt ? '可编辑视频描述（默认来自视频脚本）' : '描述你想创造的视频…'
              }
              value={promptText || defaultPrompt}
              onChange={(e) => {
                setPromptText(e.target.value)
              }}
              rows={3}
              className="min-h-[80px] resize-none text-sm"
            />
            <div className="flex flex-wrap items-center gap-2">
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline" size="sm" className="h-8 gap-1.5 rounded-lg text-sm">
                    <Sparkles className="h-3.5 w-3.5" />
                    {VIDEO_MODELS.find((m) => m.value === model)?.label ?? model}
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="start">
                  {VIDEO_MODELS.map((m) => (
                    <DropdownMenuItem
                      key={m.value}
                      onClick={() => {
                        setModel(m.value)
                      }}
                      className={model === m.value ? 'bg-accent' : undefined}
                    >
                      {m.label}
                    </DropdownMenuItem>
                  ))}
                </DropdownMenuContent>
              </DropdownMenu>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline" size="sm" className="h-8 gap-1.5 rounded-lg text-sm">
                    <Clock className="h-3.5 w-3.5" />
                    {duration}s
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="start">
                  {getVideoDurations(model).map((d) => (
                    <DropdownMenuItem
                      key={d}
                      onClick={() => {
                        setDuration(d)
                      }}
                      className={duration === d ? 'bg-accent' : undefined}
                    >
                      {d} 秒
                    </DropdownMenuItem>
                  ))}
                </DropdownMenuContent>
              </DropdownMenu>
              <Button
                size="sm"
                className="h-8 rounded-lg"
                onClick={handleCreate}
                disabled={
                  createMutation.isPending || !jobId || (!promptText.trim() && !defaultPrompt)
                }
              >
                {createMutation.isPending ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  '开始生成'
                )}
              </Button>
            </div>
            {!jobId && <p className="text-xs text-muted-foreground">请先运行一次步骤以创建任务</p>}
          </div>
        )}
      </div>
    </div>
  )
}
