/**
 * 紧凑版视频任务创建表单 - 用于聊天页底部统一输入区
 * 提示词 + 参考图输入/预览 + 模型/时长 + 创建按钮；市场固定默认值
 */

import { useState, useRef, useEffect, useMemo } from 'react'

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import { ImagePlus, Loader2, Plus, X, AlertCircle, Sparkles, Clock } from 'lucide-react'

import { ApiError } from '@/api/client'
import { videoTaskApi } from '@/api/videoTask'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { VIDEO_TASK_EXAMPLE_PROMPTS } from '@/constants/video-task'
import { useToast } from '@/hooks/use-toast'
import { cn } from '@/lib/utils'
import type { VideoGenTask, VideoModel, VideoDuration } from '@/types/video-task'

const MODELS: { value: VideoModel; label: string }[] = [
  { value: 'openai::sora1.0', label: 'Sora 1.0' },
  { value: 'openai::sora2.0', label: 'Sora 2.0' },
]

function getDurations(model: VideoModel): VideoDuration[] {
  if (model === 'openai::sora2.0') return [5, 10, 15]
  return [5, 10, 15, 20]
}

export interface VideoCreateParams {
  promptText: string
  model: VideoModel
  duration: VideoDuration
  referenceImages: string[]
}

export interface VideoTaskCreateFormCompactProps {
  /** 有则直接创建到该会话；无则通过 onVideoCreateWithoutSession 由父组件先建会话再创建 */
  sessionId?: string
  onTaskCreated?: (task: VideoGenTask) => void
  onSessionForbidden?: () => void
  /** 无 sessionId 时提交时调用，父组件负责先建会话再创建任务 */
  onVideoCreateWithoutSession?: (params: VideoCreateParams) => Promise<void>
  disabled?: boolean
}

export default function VideoTaskCreateFormCompact({
  sessionId,
  onTaskCreated,
  onSessionForbidden,
  onVideoCreateWithoutSession,
  disabled = false,
}: VideoTaskCreateFormCompactProps): React.JSX.Element {
  const [promptText, setPromptText] = useState('')
  const [model, setModel] = useState<VideoModel>('openai::sora2.0')
  const [duration, setDuration] = useState<VideoDuration>(15)
  const [referenceImages, setReferenceImages] = useState('')
  const [showImageInput, setShowImageInput] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const imageInputRef = useRef<HTMLTextAreaElement>(null)
  const queryClient = useQueryClient()
  const { toast } = useToast()

  const selectedModel = MODELS.find((m) => m.value === model)
  const availableDurations = useMemo(() => getDurations(model), [model])

  const imageUrls = useMemo(() => {
    return referenceImages
      .split('\n')
      .map((s) => s.trim())
      .filter((url) => url.length > 0 && (url.startsWith('http://') || url.startsWith('https://')))
  }, [referenceImages])

  const [imageStates, setImageStates] = useState<Record<string, 'loading' | 'loaded' | 'error'>>({})

  useEffect(() => {
    const durations = getDurations(model)
    if (!durations.includes(duration)) setDuration(durations[0])
  }, [model, duration])

  useEffect(() => {
    const el = textareaRef.current
    if (el) {
      el.style.height = 'auto'
      el.style.height = `${String(Math.min(el.scrollHeight, 120))}px`
    }
  }, [promptText])

  useEffect(() => {
    if (showImageInput && imageInputRef.current) imageInputRef.current.focus()
  }, [showImageInput])

  const removeImage = (urlToRemove: string): void => {
    setReferenceImages((prev) =>
      prev
        .split('\n')
        .filter((line) => line.trim() !== urlToRemove)
        .join('\n')
    )
  }

  const handleImageLoad = (url: string): void => {
    setImageStates((prev) => ({ ...prev, [url]: 'loaded' }))
  }

  const handleImageError = (url: string): void => {
    setImageStates((prev) => ({ ...prev, [url]: 'error' }))
  }

  const refImages = useMemo(
    () =>
      referenceImages
        .split('\n')
        .map((s) => s.trim())
        .filter(Boolean),
    [referenceImages]
  )

  const createMutation = useMutation({
    mutationFn: () => {
      if (!sessionId) throw new Error('session id required')
      return videoTaskApi.create({
        sessionId,
        promptText: promptText.trim() || undefined,
        promptSource: 'user_provided',
        marketplace: 'jp',
        model,
        duration,
        referenceImages: refImages,
        autoSubmit: true,
      })
    },
    onSuccess: (task) => {
      void queryClient.invalidateQueries({ queryKey: ['video-tasks'] })
      toast({ title: '开始创作', description: '视频正在生成中' })
      onTaskCreated?.(task)
      setPromptText('')
      setReferenceImages('')
      setShowImageInput(false)
    },
    onError: (error) => {
      const is403 = error instanceof ApiError && error.status === 403
      if (is403) {
        toast({
          variant: 'destructive',
          title: '无权限使用该会话',
          description: '请在自己的会话中创建，或前往新建页面创建。',
        })
        onSessionForbidden?.()
      } else {
        toast({
          variant: 'destructive',
          title: '创建失败',
          description: error instanceof Error ? error.message : '未知错误',
        })
      }
    },
  })

  const [withoutSessionPending, setWithoutSessionPending] = useState(false)

  const handleSubmit = async (): Promise<void> => {
    if (!promptText.trim() || disabled) return
    if (sessionId) {
      if (createMutation.isPending) return
      void createMutation.mutateAsync()
      return
    }
    if (!onVideoCreateWithoutSession || withoutSessionPending) return
    setWithoutSessionPending(true)
    try {
      await onVideoCreateWithoutSession({
        promptText: promptText.trim(),
        model,
        duration,
        referenceImages: refImages,
      })
      toast({ title: '开始创作', description: '视频正在生成中' })
      setPromptText('')
      setReferenceImages('')
      setShowImageInput(false)
    } catch {
      // 父组件 / toast 已处理错误
    } finally {
      setWithoutSessionPending(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent): void => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault()
      void handleSubmit()
    }
  }

  const isPending = sessionId ? createMutation.isPending : withoutSessionPending
  const canSubmit = promptText.trim().length > 0 && !disabled && !isPending

  return (
    <div
      className={cn(
        'relative flex flex-col rounded-2xl border border-border bg-muted/30 shadow-sm transition-all duration-200',
        'focus-within:border-primary/50 focus-within:shadow-md focus-within:ring-2 focus-within:ring-primary/10'
      )}
    >
      {/* 参考图缩略图与添加按钮 */}
      <AnimatePresence>
        {imageUrls.length > 0 && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="border-b border-border/20 px-3 py-2"
          >
            <div className="flex items-center gap-1.5">
              {imageUrls.map((url, index) => (
                <motion.div
                  key={url}
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.8 }}
                  transition={{ delay: index * 0.02 }}
                  className="group relative"
                >
                  <div className="relative h-10 w-10 overflow-hidden rounded-lg bg-muted/30">
                    {imageStates[url] !== 'error' ? (
                      <>
                        {imageStates[url] !== 'loaded' && (
                          <div className="absolute inset-0 flex items-center justify-center">
                            <Loader2 className="h-2.5 w-2.5 animate-spin text-muted-foreground/40" />
                          </div>
                        )}
                        <img
                          src={url}
                          alt={`参考图 ${String(index + 1)}`}
                          className={cn(
                            'h-full w-full object-cover',
                            imageStates[url] === 'loaded' ? 'opacity-100' : 'opacity-0'
                          )}
                          referrerPolicy="no-referrer"
                          onLoad={() => {
                            handleImageLoad(url)
                          }}
                          onError={() => {
                            handleImageError(url)
                          }}
                        />
                      </>
                    ) : (
                      <div className="flex h-full w-full items-center justify-center">
                        <AlertCircle className="h-2.5 w-2.5 text-muted-foreground/40" />
                      </div>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      removeImage(url)
                    }}
                    aria-label={`移除参考图 ${String(index + 1)}`}
                    className="absolute -right-0.5 -top-0.5 flex h-3.5 w-3.5 items-center justify-center rounded-full bg-foreground text-background opacity-0 transition-opacity group-hover:opacity-100"
                  >
                    <X className="h-2 w-2" />
                  </button>
                </motion.div>
              ))}
              <button
                type="button"
                onClick={() => {
                  setShowImageInput(true)
                }}
                aria-label="添加参考图"
                className="flex h-10 w-10 items-center justify-center rounded-lg border border-dashed border-border/50 text-muted-foreground/40 transition-colors hover:border-border hover:text-muted-foreground"
              >
                <Plus className="h-3.5 w-3.5" />
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* 预设提示词 - 与视频任务页一致 */}
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 border-b border-border/20 px-3 py-2">
        <span className="text-[11px] text-muted-foreground/50">试试：</span>
        <div className="flex flex-wrap gap-1">
          {VIDEO_TASK_EXAMPLE_PROMPTS.map((prompt, i) => (
            <button
              key={i}
              type="button"
              onClick={() => {
                setPromptText(prompt.full)
              }}
              className={cn(
                'rounded-full px-2.5 py-0.5 text-[11px] transition-all duration-200',
                promptText === prompt.full
                  ? 'bg-primary/10 text-primary'
                  : 'text-muted-foreground/60 hover:text-muted-foreground'
              )}
            >
              {prompt.short}
            </button>
          ))}
        </div>
      </div>

      <div className="px-4 py-3">
        <textarea
          ref={textareaRef}
          placeholder="描述你想创造的视频..."
          value={promptText}
          onChange={(e) => {
            setPromptText(e.target.value)
          }}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          maxLength={2000}
          rows={1}
          className="w-full resize-none bg-transparent text-[15px] leading-relaxed placeholder:text-muted-foreground focus:outline-none disabled:cursor-not-allowed"
          style={{ minHeight: '40px', maxHeight: '120px' }}
        />
      </div>
      <div className="flex items-center justify-between border-t border-border/30 px-2 py-1.5">
        <div className="flex items-center gap-0.5">
          <Button
            variant="ghost"
            size="sm"
            aria-label={showImageInput ? '收起参考图输入' : '添加参考图'}
            onClick={() => {
              setShowImageInput((v) => !v)
            }}
            className={cn(
              'h-8 w-8 rounded-lg p-0 text-muted-foreground/70 hover:bg-secondary hover:text-foreground',
              showImageInput && 'text-foreground'
            )}
          >
            <ImagePlus className="h-3.5 w-3.5" />
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                aria-label={`模型：${selectedModel?.label ?? model}`}
                className="h-8 gap-1 rounded-lg px-2 text-xs text-muted-foreground/70 hover:bg-secondary hover:text-foreground"
              >
                <Sparkles className="h-3.5 w-3.5" />
                <span>{selectedModel?.label}</span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="min-w-[120px]">
              {MODELS.map((m) => (
                <DropdownMenuItem
                  key={m.value}
                  onClick={() => {
                    setModel(m.value)
                  }}
                  className={cn('text-sm', model === m.value && 'bg-accent')}
                >
                  {m.label}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                aria-label={`时长：${String(duration)} 秒`}
                className="h-8 gap-1 rounded-lg px-2 text-xs text-muted-foreground/70 hover:bg-secondary hover:text-foreground"
              >
                <Clock className="h-3.5 w-3.5" />
                <span>{duration}s</span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="min-w-[90px]">
              {availableDurations.map((d) => (
                <DropdownMenuItem
                  key={d}
                  onClick={() => {
                    setDuration(d)
                  }}
                  className={cn('text-sm', duration === d && 'bg-accent')}
                >
                  {d} 秒
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
        <Button
          size="sm"
          onClick={handleSubmit}
          disabled={!canSubmit}
          className={cn(
            'h-8 rounded-lg px-3 text-xs font-medium transition-all',
            canSubmit
              ? 'bg-primary text-primary-foreground hover:bg-primary/90'
              : 'bg-muted text-muted-foreground/50'
          )}
        >
          {isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : '创建'}
        </Button>
      </div>

      {/* 图片链接输入 */}
      <AnimatePresence>
        {showImageInput && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="overflow-hidden border-t border-border/20"
          >
            <div className="px-3 py-2">
              <textarea
                ref={imageInputRef}
                placeholder="粘贴图片链接（每行一个）"
                value={referenceImages}
                onChange={(e) => {
                  setReferenceImages(e.target.value)
                }}
                rows={2}
                className="w-full resize-none bg-transparent text-sm placeholder:text-muted-foreground/40 focus:outline-none"
              />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
