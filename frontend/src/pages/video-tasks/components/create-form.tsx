import { useState, useRef, useEffect, useMemo } from 'react'

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import { ImagePlus, Loader2, X, AlertCircle, Plus, Sparkles, Clock } from 'lucide-react'

import { videoTaskApi } from '@/api/videoTask'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { VIDEO_TASK_MARKETPLACES } from '@/constants/video-task'
import { useToast } from '@/hooks/use-toast'
import { cn } from '@/lib/utils'
import type { VideoGenTask, VideoModel, VideoDuration } from '@/types/video-task'

interface VideoTaskCreateFormProps {
  onTaskCreated?: (task: VideoGenTask) => void
  disabled?: boolean
  initialPrompt?: string
  sessionId?: string
}

const models: { value: VideoModel; label: string; description: string }[] = [
  { value: 'openai::sora1.0', label: 'Sora 1.0', description: '快速生成' },
  { value: 'openai::sora2.0', label: 'Sora 2.0', description: '高质量' },
]

// 根据模型获取可用时长
const getDurations = (model: VideoModel): VideoDuration[] => {
  if (model === 'openai::sora2.0') {
    return [5, 10, 15]
  }
  return [5, 10, 15, 20]
}

/**
 * 创建表单 - 乔布斯美学
 *
 * 设计理念：
 * - 极简：只保留必要元素
 * - 聚焦：输入框是唯一主角
 * - 呼吸：充足的内边距和留白
 */
export default function VideoTaskCreateForm({
  onTaskCreated,
  disabled = false,
  initialPrompt,
  sessionId,
}: VideoTaskCreateFormProps): React.JSX.Element {
  const [promptText, setPromptText] = useState(initialPrompt ?? '')
  const [marketplace, setMarketplace] = useState('jp')
  const [model, setModel] = useState<VideoModel>('openai::sora2.0')
  const [duration, setDuration] = useState<VideoDuration>(15)
  const [referenceImages, setReferenceImages] = useState('')
  const [showImageInput, setShowImageInput] = useState(false)
  const [isFocused, setIsFocused] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const imageInputRef = useRef<HTMLTextAreaElement>(null)
  const queryClient = useQueryClient()
  const { toast } = useToast()

  const selectedMarketplace = VIDEO_TASK_MARKETPLACES.find((m) => m.value === marketplace)
  const selectedModel = models.find((m) => m.value === model)
  const availableDurations = useMemo(() => getDurations(model), [model])

  // 当模型变化时，确保时长在可用范围内
  useEffect(() => {
    const durations = getDurations(model)
    if (!durations.includes(duration)) {
      setDuration(durations[0])
    }
  }, [model, duration])

  // 解析图片 URL 列表
  const imageUrls = useMemo(() => {
    return referenceImages
      .split('\n')
      .map((s) => s.trim())
      .filter((url) => url.length > 0 && (url.startsWith('http://') || url.startsWith('https://')))
  }, [referenceImages])

  // 图片加载状态
  const [imageStates, setImageStates] = useState<Record<string, 'loading' | 'loaded' | 'error'>>({})

  // 响应外部传入的初始提示词变化
  useEffect(() => {
    if (initialPrompt) {
      setPromptText(initialPrompt)
    }
  }, [initialPrompt])

  // 自动调整输入框高度
  useEffect(() => {
    const textarea = textareaRef.current
    if (textarea) {
      textarea.style.height = 'auto'
      textarea.style.height = `${Math.min(textarea.scrollHeight, 160)}px`
    }
  }, [promptText])

  // 聚焦到图片输入框
  useEffect(() => {
    if (showImageInput && imageInputRef.current) {
      imageInputRef.current.focus()
    }
  }, [showImageInput])

  // 移除某个图片
  const removeImage = (urlToRemove: string): void => {
    const lines = referenceImages.split('\n')
    const filtered = lines.filter((line) => line.trim() !== urlToRemove)
    setReferenceImages(filtered.join('\n'))
  }

  // 处理图片加载状态
  const handleImageLoad = (url: string): void => {
    setImageStates((prev) => ({ ...prev, [url]: 'loaded' }))
  }

  const handleImageError = (url: string): void => {
    setImageStates((prev) => ({ ...prev, [url]: 'error' }))
  }

  const createMutation = useMutation({
    mutationFn: () =>
      videoTaskApi.create({
        sessionId,
        promptText: promptText || undefined,
        promptSource: 'user_provided',
        marketplace,
        model,
        duration,
        referenceImages: referenceImages
          .split('\n')
          .map((s) => s.trim())
          .filter(Boolean),
        autoSubmit: true,
      }),
    onSuccess: (task) => {
      void queryClient.invalidateQueries({ queryKey: ['video-tasks'] })
      toast({ title: '开始创作', description: '视频正在生成中' })
      onTaskCreated?.(task)
      setPromptText('')
      setReferenceImages('')
      setShowImageInput(false)
    },
    onError: (error) => {
      toast({
        variant: 'destructive',
        title: '创建失败',
        description: error instanceof Error ? error.message : '未知错误',
      })
    },
  })

  const handleSubmit = (): void => {
    if (!promptText.trim() || disabled || createMutation.isPending) return
    void createMutation.mutateAsync()
  }

  const handleKeyDown = (e: React.KeyboardEvent): void => {
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault()
      handleSubmit()
    }
  }

  const canSubmit = promptText.trim().length > 0 && !disabled && !createMutation.isPending

  return (
    <div
      className={cn(
        'relative rounded-2xl border bg-background/80 backdrop-blur-xl transition-all duration-300',
        isFocused ? 'border-border/60 shadow-lg' : 'border-border/40 shadow-md',
        disabled && 'opacity-60'
      )}
    >
      {/* 图片缩略图区域 */}
      <AnimatePresence>
        {imageUrls.length > 0 && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: [0.23, 1, 0.32, 1] }}
            className="border-b border-border/20 px-4 py-3"
          >
            <div className="flex items-center gap-2">
              {imageUrls.map((url, index) => (
                <motion.div
                  key={url}
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.8 }}
                  transition={{ delay: index * 0.02 }}
                  className="group relative"
                >
                  <div className="relative h-12 w-12 overflow-hidden rounded-lg bg-muted/30">
                    {imageStates[url] !== 'error' ? (
                      <>
                        {imageStates[url] !== 'loaded' && (
                          <div className="absolute inset-0 flex items-center justify-center">
                            <Loader2 className="h-3 w-3 animate-spin text-muted-foreground/40" />
                          </div>
                        )}
                        <img
                          src={url}
                          alt={`参考图 ${index + 1}`}
                          className={cn(
                            'h-full w-full object-cover',
                            imageStates[url] === 'loaded' ? 'opacity-100' : 'opacity-0'
                          )}
                          onLoad={() => { handleImageLoad(url); }}
                          onError={() => { handleImageError(url); }}
                        />
                      </>
                    ) : (
                      <div className="flex h-full w-full items-center justify-center">
                        <AlertCircle className="h-3 w-3 text-muted-foreground/40" />
                      </div>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => { removeImage(url); }}
                    aria-label={`移除参考图 ${index + 1}`}
                    className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-foreground text-background opacity-0 transition-opacity group-hover:opacity-100"
                  >
                    <X className="h-2.5 w-2.5" />
                  </button>
                </motion.div>
              ))}
              {/* 添加更多 */}
              <button
                type="button"
                onClick={() => { setShowImageInput(true); }}
                aria-label="添加参考图"
                className="flex h-12 w-12 items-center justify-center rounded-lg border border-dashed border-border/50 text-muted-foreground/40 transition-colors hover:border-border hover:text-muted-foreground"
              >
                <Plus className="h-4 w-4" />
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* 主输入区域 */}
      <div className="px-5 py-4">
        <textarea
          ref={textareaRef}
          placeholder="描述你想创造的视频..."
          value={promptText}
          onChange={(e) => { setPromptText(e.target.value); }}
          onFocus={() => { setIsFocused(true); }}
          onBlur={() => { setIsFocused(false); }}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          maxLength={2000}
          rows={2}
          className={cn(
            'w-full resize-none bg-transparent text-[15px] leading-relaxed',
            'placeholder:text-muted-foreground/40',
            'focus:outline-none',
            'disabled:cursor-not-allowed'
          )}
          style={{ minHeight: '48px', maxHeight: '160px' }}
        />
        {promptText.length > 1800 && (
          <p className="mt-1 text-right text-xs text-muted-foreground/40">
            {promptText.length}/2000
          </p>
        )}
      </div>

      {/* 底部工具栏 - 极简 */}
      <div className="flex items-center justify-between border-t border-border/20 px-4 py-2.5">
        <div className="flex items-center gap-1">
          {/* 市场选择 */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                aria-label={`目标站点：${selectedMarketplace?.label ?? marketplace}`}
                className="h-7 w-7 rounded-lg p-0 text-muted-foreground/60 hover:text-foreground"
              >
                <span className="text-sm">{selectedMarketplace?.flag}</span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="min-w-[120px]">
              {VIDEO_TASK_MARKETPLACES.map((m) => (
                <DropdownMenuItem
                  key={m.value}
                  onClick={() => { setMarketplace(m.value); }}
                  className={cn('text-sm', marketplace === m.value && 'bg-accent')}
                >
                  {m.label}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>

          {/* 模型选择 */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                aria-label={`模型：${selectedModel?.label ?? model}`}
                className="h-7 gap-1.5 rounded-lg px-2 text-xs text-muted-foreground/60 hover:text-foreground"
              >
                <Sparkles className="h-3 w-3" />
                <span>{selectedModel?.label}</span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="min-w-[140px]">
              {models.map((m) => (
                <DropdownMenuItem
                  key={m.value}
                  onClick={() => { setModel(m.value); }}
                  className={cn('text-sm', model === m.value && 'bg-accent')}
                >
                  <div className="flex flex-col">
                    <span>{m.label}</span>
                    <span className="text-xs text-muted-foreground">{m.description}</span>
                  </div>
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>

          {/* 时长选择 */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                aria-label={`时长：${duration} 秒`}
                className="h-7 gap-1.5 rounded-lg px-2 text-xs text-muted-foreground/60 hover:text-foreground"
              >
                <Clock className="h-3 w-3" />
                <span>{duration}s</span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="min-w-[100px]">
              {availableDurations.map((d) => (
                <DropdownMenuItem
                  key={d}
                  onClick={() => { setDuration(d); }}
                  className={cn('text-sm', duration === d && 'bg-accent')}
                >
                  {d} 秒
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>

          {/* 添加图片 */}
          <Button
            variant="ghost"
            size="sm"
            aria-label={showImageInput ? '收起参考图输入' : '添加参考图'}
            onClick={() => { setShowImageInput(!showImageInput); }}
            className={cn(
              'h-7 w-7 rounded-lg p-0 text-muted-foreground/60 hover:text-foreground',
              showImageInput && 'text-foreground'
            )}
          >
            <ImagePlus className="h-4 w-4" />
          </Button>
        </div>

        {/* 发送按钮 */}
        <Button
          onClick={handleSubmit}
          disabled={!canSubmit}
          size="sm"
          className={cn(
            'h-7 rounded-lg px-3 text-xs font-medium transition-all',
            canSubmit
              ? 'bg-foreground text-background hover:bg-foreground/90'
              : 'bg-muted text-muted-foreground'
          )}
        >
          {createMutation.isPending ? (
            <Loader2 className="h-3 w-3 animate-spin" />
          ) : (
            '创建'
          )}
        </Button>
      </div>

      {/* 图片 URL 输入 */}
      <AnimatePresence>
        {showImageInput && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="overflow-hidden border-t border-border/20"
          >
            <div className="px-4 py-3">
              <textarea
                ref={imageInputRef}
                placeholder="粘贴图片链接（每行一个）"
                value={referenceImages}
                onChange={(e) => { setReferenceImages(e.target.value); }}
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
