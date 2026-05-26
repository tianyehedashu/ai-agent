/**
 * 8 图生成：模型选择（系统+用户）、参考图输入、8 槽提示词编辑、生成主图。
 */

import { useState, useMemo, useCallback, memo } from 'react'

import { ModelSelector } from '@/components/model-selector'
import { Button } from '@/components/ui/button'
import { ImageLightbox } from '@/components/ui/image-lightbox'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { ImageGenSizePresetPicker } from '@/features/gateway-shared/image-gen-size-preset-picker'
import { useCopyToClipboardKeyed } from '@/hooks/use-copy-to-clipboard'
import type { ListingStudioCapabilitiesConfig } from '@/hooks/use-listing-studio-capabilities'
import { useToast } from '@/hooks/use-toast'
import { ImagePlus, Loader2, Copy, Check, Settings2 } from '@/lib/lucide-icons'
import { OverlayScope } from '@/lib/ui-overlay'
import { cn } from '@/lib/utils'
import type { ListingStudioJob, ProductImageGenTask } from '@/types/listing-studio'

import { ImageUrlListEditor } from './input-panel'
import { SlotRegeneratePopover } from './slot-regenerate-popover'

import type {
  UseListingStudioImageGenResult,
  SlotReferenceMode,
} from '../hooks/use-listing-studio-image-gen'

const SLOT_LABELS = ['第1张（白底）', '第2张', '第3张', '第4张', '第5张', '第6张', '第7张', '第8张']

interface ImageGenPanelProps {
  currentJob: ListingStudioJob | null
  prompts: string[]
  onPromptsChange: (prompts: string[]) => void
  capabilityConfig: ListingStudioCapabilitiesConfig
  imageGen: UseListingStudioImageGenResult
}

export function ImageGenPanel({
  currentJob,
  prompts,
  onPromptsChange,
  capabilityConfig: caps,
  imageGen,
}: ImageGenPanelProps): React.JSX.Element {
  const [copyPrompt, copiedIndex] = useCopyToClipboardKeyed()
  const [lightboxUrl, setLightboxUrl] = useState<string | null>(null)
  const [showSettings, setShowSettings] = useState(false)

  const { toast } = useToast()

  const {
    modelId,
    setModelId,
    setSize,
    effectiveSize,
    selectedProvider,
    referenceImageUrls,
    setReferenceImageUrls,
    strength,
    setStrength,
    sourceImageUrl,
    tasks,
    isCreating,
    regeneratingSlot,
    createAll,
    regenerateSlot,
    generateSingleSlot,
  } = imageGen

  const outputKey = caps.outputKeys.image_gen_prompts
  const step5 = currentJob?.steps?.find((s) => s.capability_id === 'image_gen_prompts')
  const fromStep5 = useMemo(() => {
    const step5Prompts = step5?.output_snapshot?.[outputKey]
    return Array.isArray(step5Prompts) ? step5Prompts.map(String).slice(0, 8) : []
  }, [step5?.output_snapshot, outputKey])

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

  const paddedPrompts = useMemo(() => {
    const next = [...prompts]
    while (next.length < 8) next.push('')
    return next
  }, [prompts])

  const handlePreview = useCallback((url: string) => {
    setLightboxUrl(url)
  }, [])

  return (
    <OverlayScope>
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
          </div>

          <ImageGenSizePresetPicker
            layout="compact"
            provider={selectedProvider}
            size={effectiveSize}
            onSizeChange={setSize}
          />

          {showSettings ? (
            <div className="mt-4 space-y-4 border-t border-border/30 pt-4">
              <ImageUrlListEditor
                urls={referenceImageUrls}
                onChange={setReferenceImageUrls}
                label="生图参考图（img2img，优先于输入区原图）"
                compact
              />
              {sourceImageUrl ? (
                <p className="text-xs text-muted-foreground">
                  当前生图参考图：
                  <span className="ml-1 font-mono">{sourceImageUrl.slice(0, 48)}…</span>
                </p>
              ) : null}
              {(referenceImageUrls.length > 0 || sourceImageUrl) && (
                <div className="flex items-center gap-3">
                  <Label className="whitespace-nowrap text-sm text-muted-foreground">
                    参考强度
                  </Label>
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
          ) : null}
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
            {SLOT_LABELS.map((label, i) => {
              const slot = i + 1
              const isSlotBusy = isCreating && regeneratingSlot === slot
              return (
                <div key={i} className="flex flex-col gap-2">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-medium text-muted-foreground">{label}</span>
                    <div className="flex items-center gap-1">
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-7 px-2 text-xs"
                        disabled={isCreating || !paddedPrompts[i]?.trim()}
                        onClick={() => {
                          generateSingleSlot(slot)
                        }}
                      >
                        {isSlotBusy ? <Loader2 className="h-3 w-3 animate-spin" /> : '生成此张'}
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-7 w-7 rounded-md p-0"
                        onClick={() => copyPrompt(paddedPrompts[i] ?? '', i)}
                      >
                        {copiedIndex === i ? (
                          <Check className="h-3.5 w-3.5" />
                        ) : (
                          <Copy className="h-3.5 w-3.5" />
                        )}
                      </Button>
                    </div>
                  </div>
                  <Textarea
                    value={paddedPrompts[i] ?? ''}
                    onChange={(e) => {
                      setPrompt(i, e.target.value)
                    }}
                    placeholder={i === 0 ? '白底产品图…' : '提示词…'}
                    rows={2}
                    className="rounded-xl border-border/60 font-mono text-sm"
                  />
                </div>
              )
            })}
          </div>
          <Button className="mt-4 rounded-xl" onClick={createAll} disabled={isCreating}>
            {isCreating && regeneratingSlot === null ? (
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
                  onPreview={handlePreview}
                  onRegenerate={regenerateSlot}
                  isCreating={isCreating}
                  regeneratingSlot={regeneratingSlot}
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
    </OverlayScope>
  )
}

const STATUS_MAP: Record<string, { label: string; color: string }> = {
  pending: { label: '等待中…', color: 'text-amber-600' },
  running: { label: '生成中…', color: 'text-blue-600' },
  completed: { label: '已完成', color: 'text-emerald-600' },
  failed: { label: '失败', color: 'text-destructive' },
}

const TaskResultCard = memo(function TaskResultCard({
  task,
  onPreview,
  onRegenerate,
  isCreating,
  regeneratingSlot,
}: {
  task: ProductImageGenTask
  onPreview: (url: string) => void
  onRegenerate: (slot: number, mode: SlotReferenceMode) => void
  isCreating: boolean
  regeneratingSlot: number | null
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
            images.map((img) => {
              const slot = img.slot
              const isRegenerating = isCreating && regeneratingSlot === slot
              return img.url ? (
                <div
                  key={slot}
                  className="group relative aspect-square overflow-hidden rounded-lg border border-border/60 bg-muted"
                >
                  <button
                    type="button"
                    className="h-full w-full transition-transform hover:scale-[1.02]"
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
                  <div
                    className={cn(
                      'absolute inset-0 flex flex-col items-center justify-center gap-1 bg-black/50 opacity-0 transition-opacity group-hover:opacity-100',
                      isRegenerating && 'opacity-100'
                    )}
                  >
                    {isRegenerating ? (
                      <Loader2 className="h-5 w-5 animate-spin text-white" />
                    ) : (
                      <SlotRegeneratePopover
                        slot={slot}
                        disabled={isCreating}
                        isRegenerating={false}
                        onRegenerate={onRegenerate}
                        variant="overlay"
                      />
                    )}
                  </div>
                </div>
              ) : (
                <div
                  key={slot}
                  className="flex aspect-square items-center justify-center rounded-lg border border-border/40 bg-muted/30 text-xs text-muted-foreground/50"
                >
                  {img.error ? '!' : slot}
                </div>
              )
            })
          )}
        </div>
      )}
    </div>
  )
})
