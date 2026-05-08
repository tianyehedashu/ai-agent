/**
 * 8 图生成：模型选择（系统+用户）、参考图输入、8 槽提示词编辑、生成主图。
 */

import { useState, useMemo } from 'react'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ImagePlus, Loader2, Copy, Check, Settings2 } from 'lucide-react'

import { productInfoApi } from '@/api/productInfo'
import { userModelApi } from '@/api/userModel'
import { ModelSelector } from '@/components/model-selector'
import { Button } from '@/components/ui/button'
import { ImageLightbox } from '@/components/ui/image-lightbox'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { useCopyToClipboardKeyed } from '@/hooks/use-copy-to-clipboard'
import { useProductInfoCapabilities } from '@/hooks/use-product-info-capabilities'
import { useToast } from '@/hooks/use-toast'
import type { ProductInfoJob, ProductImageGenTask } from '@/types/product-info'

import { ImageUrlListEditor } from './input-panel'

interface ImageGenPanelProps {
  currentJob: ProductInfoJob | null
  prompts: string[]
  onPromptsChange: (prompts: string[]) => void
}

const SLOT_LABELS = ['第1张（白底）', '第2张', '第3张', '第4张', '第5张', '第6张', '第7张', '第8张']

const PROVIDER_SIZE_MAP: Record<string, string[]> = {
  volcengine: ['1920x1920', '1080x1920', '1920x1080'],
  openai: ['1024x1024', '1024x1792', '1792x1024'],
}
const DEFAULT_SIZES = ['1024x1024', '1920x1920']

export function ImageGenPanel({
  currentJob,
  prompts,
  onPromptsChange,
}: ImageGenPanelProps): React.JSX.Element {
  const caps = useProductInfoCapabilities()
  const [copyPrompt, copiedIndex] = useCopyToClipboardKeyed()
  const [lightboxUrl, setLightboxUrl] = useState<string | null>(null)
  const [showSettings, setShowSettings] = useState(false)

  const [modelId, setModelId] = useState<string | null>(null)
  const [size, setSize] = useState('')
  const [referenceImageUrls, setReferenceImageUrls] = useState<string[]>([])
  const [strength, setStrength] = useState(0.7)

  const queryClient = useQueryClient()
  const { toast } = useToast()

  const { data: availableData } = useQuery({
    queryKey: ['user-models', 'available', 'image_gen'],
    queryFn: () => userModelApi.listAvailable('image_gen'),
    staleTime: 30_000,
  })

  const selectedProvider = useMemo(() => {
    if (!modelId || !availableData) return 'volcengine'
    const sys = availableData.system_models.find((m) => m.id === modelId)
    if (sys) return sys.provider
    const user = availableData.user_models.find((m) => m.id === modelId)
    if (user) return user.provider
    return 'volcengine'
  }, [modelId, availableData])

  const sizeOptions = PROVIDER_SIZE_MAP[selectedProvider] ?? DEFAULT_SIZES
  const effectiveSize = size && sizeOptions.includes(size) ? size : sizeOptions[0]

  const outputKey = caps.outputKeys.image_gen_prompts
  const step5 = currentJob?.steps?.find((s) => s.capability_id === 'image_gen_prompts')
  const step5Prompts = step5?.output_snapshot?.[outputKey]
  const fromStep5 = Array.isArray(step5Prompts) ? step5Prompts.map(String).slice(0, 8) : []

  const { data: tasksData } = useQuery({
    queryKey: ['product-info', 'image-gen-tasks'],
    queryFn: () => productInfoApi.listImageGenTasks({ limit: 10 }),
    refetchInterval: (query) => {
      const data = query.state.data as { items?: { status: string }[] } | undefined
      const hasActive = data?.items?.some((t) => t.status === 'pending' || t.status === 'running')
      return hasActive ? 3000 : false
    },
  })
  const tasks = tasksData?.items ?? []

  const createMutation = useMutation({
    mutationFn: async () => {
      const firstRef = referenceImageUrls[0] ?? ''
      const hasRef = firstRef !== ''
      const body: Parameters<typeof productInfoApi.createImageGenTask>[0] = {
        prompts: prompts.slice(0, 8).map((p, slot) => ({ slot: slot + 1, prompt: p })),
        job_id: currentJob?.id,
        model_id: modelId,
        size: effectiveSize,
        reference_image_url: hasRef ? firstRef : null,
        strength: hasRef ? strength : null,
      }
      return productInfoApi.createImageGenTask(body)
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['product-info', 'image-gen-tasks'] })
      toast({ title: '已提交生成，主图将显示在下方' })
    },
    onError: (err) => {
      toast({ title: '创建失败', description: String(err), variant: 'destructive' })
    },
  })

  const fillFromStep5 = (): void => {
    if (fromStep5.length) {
      const next = [...fromStep5]
      while (next.length < 8) next.push('')
      onPromptsChange(next.slice(0, 8))
      toast({ title: '已从「8 图生成提示词」步骤填充' })
    } else {
      toast({ title: '请先运行「8 图生成提示词」步骤', variant: 'destructive' })
    }
  }

  const setPrompt = (index: number, value: string): void => {
    const next = [...prompts]
    while (next.length <= index) next.push('')
    next[index] = value
    onPromptsChange(next.slice(0, 8))
  }

  const currentPrompts = [...prompts]
  while (currentPrompts.length < 8) currentPrompts.push('')

  return (
    <div className="space-y-6">
      {/* 生成设置 */}
      <div className="rounded-xl border border-border/50 bg-card/80 p-5 shadow-sm">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <Settings2 className="h-4 w-4" />
            </span>
            <Label className="text-base font-semibold tracking-tight">生成设置</Label>
          </div>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="rounded-lg"
            onClick={() => {
              setShowSettings(!showSettings)
            }}
          >
            {showSettings ? '收起' : '展开'}
          </Button>
        </div>

        {/* 模型 + 尺寸 */}
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2">
            <Label className="whitespace-nowrap text-sm text-muted-foreground">模型</Label>
            <ModelSelector
              modelType="image_gen"
              value={modelId}
              onChange={setModelId}
              placeholder="默认模型"
              className="h-9 w-[220px] rounded-lg"
            />
          </div>
          <div className="flex items-center gap-2">
            <Label className="whitespace-nowrap text-sm text-muted-foreground">尺寸</Label>
            <Select value={effectiveSize} onValueChange={setSize}>
              <SelectTrigger className="h-9 w-[150px] rounded-lg">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {sizeOptions.map((s) => (
                  <SelectItem key={s} value={s}>
                    {s}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* 展开区域：参考图 + strength */}
        {showSettings && (
          <div className="mt-4 space-y-4 border-t border-border/30 pt-4">
            <ImageUrlListEditor
              urls={referenceImageUrls}
              onChange={setReferenceImageUrls}
              label="参考图片（img2img）"
              compact
            />
            {referenceImageUrls.length > 0 && (
              <div className="flex items-center gap-3">
                <Label className="whitespace-nowrap text-sm text-muted-foreground">参考强度</Label>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={strength}
                  onChange={(e) => {
                    setStrength(Number(e.target.value))
                  }}
                  className="h-2 w-48 cursor-pointer accent-primary"
                />
                <span className="min-w-[3rem] text-sm text-muted-foreground">
                  {strength.toFixed(2)}
                </span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* 8 槽提示词 */}
      <div className="rounded-xl border border-border/50 bg-card/80 p-5 shadow-sm">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <ImagePlus className="h-4 w-4" />
            </span>
            <Label className="text-base font-semibold tracking-tight">8 张主图提示词</Label>
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="rounded-lg"
            onClick={fillFromStep5}
            disabled={fromStep5.length === 0}
            title="从「8 图生成提示词」步骤填充"
          >
            从步骤填充
          </Button>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          {SLOT_LABELS.map((label, i) => (
            <div key={i} className="flex flex-col gap-2">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-muted-foreground">{label}</span>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-7 w-7 rounded-md p-0"
                  onClick={() => copyPrompt(currentPrompts[i] ?? '', i)}
                >
                  {copiedIndex === i ? (
                    <Check className="h-3.5 w-3.5" />
                  ) : (
                    <Copy className="h-3.5 w-3.5" />
                  )}
                </Button>
              </div>
              <Textarea
                value={currentPrompts[i] ?? ''}
                onChange={(e) => {
                  setPrompt(i, e.target.value)
                }}
                placeholder={i === 0 ? '白底产品图…' : '提示词…'}
                rows={2}
                className="rounded-xl border-border/60 font-mono text-sm"
              />
            </div>
          ))}
        </div>
        <Button
          className="mt-4 rounded-xl"
          onClick={() => {
            createMutation.mutate()
          }}
          disabled={createMutation.isPending}
        >
          {createMutation.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <ImagePlus className="h-4 w-4" />
          )}
          <span className="ml-2">生成 8 张主图</span>
        </Button>
      </div>

      {/* 已生成的主图 */}
      <div className="rounded-xl border border-border/50 bg-card/80 p-5 shadow-sm">
        <h3 className="mb-4 font-semibold tracking-tight">已生成的主图</h3>
        {tasks.length === 0 ? (
          <p className="py-4 text-sm text-muted-foreground">暂无记录，生成后将显示在此处</p>
        ) : (
          <div className="space-y-4">
            {tasks.map((t) => (
              <TaskResultCard
                key={t.id}
                task={t}
                onPreview={(url) => {
                  setLightboxUrl(url)
                }}
              />
            ))}
          </div>
        )}
      </div>

      <ImageLightbox
        src={lightboxUrl}
        onClose={() => {
          setLightboxUrl(null)
        }}
      />
    </div>
  )
}

const STATUS_MAP: Record<string, { label: string; color: string }> = {
  pending: { label: '等待中…', color: 'text-amber-600' },
  running: { label: '生成中…', color: 'text-blue-600' },
  completed: { label: '已完成', color: 'text-emerald-600' },
  failed: { label: '失败', color: 'text-destructive' },
}

function TaskResultCard({
  task,
  onPreview,
}: {
  task: ProductImageGenTask
  onPreview: (url: string) => void
}): React.JSX.Element {
  const images = task.result_images ?? []
  const isActive = task.status === 'pending' || task.status === 'running'
  const statusInfo = STATUS_MAP[task.status] ?? {
    label: task.status,
    color: 'text-muted-foreground',
  }

  return (
    <div className="rounded-xl border border-border/50 bg-muted/20 p-4 transition-shadow hover:shadow-md">
      <div className="mb-3 flex items-center justify-between text-sm">
        <span className={`flex items-center gap-1.5 font-medium ${statusInfo.color}`}>
          {isActive && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
          {statusInfo.label}
        </span>
        {task.status === 'failed' && task.error_message && (
          <span
            className="max-w-[60%] truncate text-xs text-muted-foreground"
            title={task.error_message}
          >
            {task.error_message}
          </span>
        )}
      </div>
      {isActive ? (
        <div className="grid grid-cols-4 gap-2.5 sm:grid-cols-8">
          {Array.from({ length: 8 }, (_, i) => (
            <div
              key={i}
              className="flex aspect-square items-center justify-center rounded-lg border border-border/40 bg-muted/30"
            >
              <Loader2 className="h-4 w-4 animate-spin text-muted-foreground/50" />
            </div>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-4 gap-2.5 sm:grid-cols-8">
          {images.length === 0 ? (
            <p className="col-span-full py-4 text-sm text-muted-foreground">暂无结果图</p>
          ) : (
            images.map((img, i) =>
              img.url ? (
                <button
                  key={i}
                  type="button"
                  className="aspect-square overflow-hidden rounded-lg border border-border/60 bg-muted transition-transform hover:scale-[1.02]"
                  onClick={() => {
                    onPreview(img.url)
                  }}
                >
                  <img
                    src={img.url}
                    alt=""
                    className="h-full w-full object-cover"
                    referrerPolicy="no-referrer"
                  />
                </button>
              ) : (
                <div
                  key={i}
                  className="flex aspect-square items-center justify-center rounded-lg border border-border/40 bg-muted/30 text-xs text-muted-foreground/50"
                >
                  {img.error ? '!' : i + 1}
                </div>
              )
            )
          )}
        </div>
      )}
    </div>
  )
}
