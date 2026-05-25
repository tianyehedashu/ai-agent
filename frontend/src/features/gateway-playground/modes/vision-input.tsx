import { useCallback, useId, useRef, useState } from 'react'
import type React from 'react'

import { Button, buttonVariants } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  formatReferenceImageIngestError,
  ingestReferenceImage,
  isImageFileCandidate,
  readImageFromClipboard,
  REFERENCE_IMAGE_ACCEPT_ERROR,
} from '@/features/gateway-playground/lib/reference-image-ingest'
import { useToast } from '@/hooks/use-toast'
import { AlertCircle, ImagePlus, Loader2, X } from '@/lib/lucide-icons'
import { cn } from '@/lib/utils'

type PreviewStatus = 'loading' | 'loaded' | 'error'

interface VisionInputProps {
  imageUrlId: string
  imageUrl: string
  onImageUrlChange: (value: string) => void
  disabled?: boolean
  label?: string
}

const PREVIEW_FRAME_CLASS =
  'relative flex min-h-[6rem] max-w-full items-center justify-center overflow-hidden rounded-md border bg-muted/30'

const HELPER_TEXT =
  '支持 JPG / PNG / WebP / GIF；图片链接、本地上传或粘贴截图；小图自动内联，大图上传至图床'

function PreviewLoadHint(): React.JSX.Element {
  return (
    <div className="flex items-center gap-2 px-3 py-6 text-xs text-muted-foreground">
      <Loader2 className="h-4 w-4 shrink-0 animate-spin" aria-hidden="true" />
      加载预览…
    </div>
  )
}

function PreviewErrorHint(): React.JSX.Element {
  return (
    <div className="flex max-w-full flex-col items-center gap-1.5 px-3 py-4 text-center text-xs text-muted-foreground">
      <AlertCircle className="h-5 w-5 shrink-0 text-muted-foreground/70" aria-hidden="true" />
      <span>浏览器无法加载该图片（常见于防盗链或跨域限制）</span>
      <span className="text-[11px] text-muted-foreground/80">
        试调请求仍可能成功；可改用 data URL 或允许外链的图床
      </span>
    </div>
  )
}

function EmptyDropZone({
  uploading,
  disabled,
  onPickFile,
}: {
  uploading: boolean
  disabled: boolean
  onPickFile: () => void
}): React.JSX.Element {
  return (
    <button
      type="button"
      className="flex w-full flex-col items-center justify-center gap-2 rounded-md border border-dashed border-border/60 bg-muted/20 py-6 text-center transition-colors hover:border-primary/40 hover:bg-muted/40 disabled:pointer-events-none disabled:opacity-50"
      onClick={onPickFile}
      disabled={disabled || uploading}
    >
      {uploading ? (
        <Loader2 className="h-7 w-7 animate-spin text-muted-foreground" aria-hidden="true" />
      ) : (
        <ImagePlus className="h-7 w-7 text-muted-foreground" aria-hidden="true" />
      )}
      <span className="text-sm text-muted-foreground">
        {uploading ? '处理中…' : '点击上传、拖拽图片，或 Ctrl+V / ⌘V 粘贴'}
      </span>
    </button>
  )
}

/** URL 变更时由父级 key 重挂载，无需 effect 同步加载态 */
function VisionImagePreview({ src }: { src: string }): React.JSX.Element {
  const [status, setStatus] = useState<PreviewStatus>('loading')
  const isLoading = status === 'loading'
  const isError = status === 'error'
  const isLoaded = status === 'loaded'

  return (
    <div className={cn(PREVIEW_FRAME_CLASS, isLoaded ? 'border-border' : null)}>
      {isLoading ? <PreviewLoadHint /> : null}
      {isError ? <PreviewErrorHint /> : null}
      {isError ? null : (
        <img
          src={src}
          alt="参考图预览"
          referrerPolicy="no-referrer"
          className={cn(
            'max-h-40 max-w-full object-contain',
            isLoaded ? 'opacity-100' : 'absolute h-0 w-0 opacity-0'
          )}
          onLoad={() => {
            setStatus('loaded')
          }}
          onError={() => {
            setStatus('error')
          }}
        />
      )}
    </div>
  )
}

export function VisionInput({
  imageUrlId,
  imageUrl,
  onImageUrlChange,
  disabled,
  label = '参考图片',
}: VisionInputProps): React.JSX.Element {
  const trimmed = imageUrl.trim()
  const hasPreview = trimmed.length > 0
  const fileInputId = useId()
  const fileRef = useRef<HTMLInputElement>(null)
  const ingestingRef = useRef(false)
  const [uploading, setUploading] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const { toast } = useToast()
  const isDisabled = Boolean(disabled)
  const isBusy = isDisabled || uploading

  const applyFile = useCallback(
    async (file: File): Promise<void> => {
      if (isDisabled || ingestingRef.current) return
      ingestingRef.current = true
      setUploading(true)
      try {
        const url = await ingestReferenceImage(file)
        onImageUrlChange(url)
      } catch (err) {
        toast({
          variant: 'destructive',
          title: '图片处理失败',
          description: formatReferenceImageIngestError(err),
        })
      } finally {
        ingestingRef.current = false
        setUploading(false)
      }
    },
    [isDisabled, onImageUrlChange, toast]
  )

  const openFilePicker = useCallback((): void => {
    fileRef.current?.click()
  }, [])

  const handleFileInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>): void => {
      const file = e.target.files?.[0]
      e.target.value = ''
      if (!file) return
      void applyFile(file)
    },
    [applyFile]
  )

  const handlePaste = useCallback(
    (e: React.ClipboardEvent): void => {
      if (isBusy) return
      const file = readImageFromClipboard(e.clipboardData)
      if (!file) return
      e.preventDefault()
      void applyFile(file)
    },
    [applyFile, isBusy]
  )

  const handleDrop = useCallback(
    (e: React.DragEvent): void => {
      e.preventDefault()
      setDragOver(false)
      if (isBusy) return
      const { files } = e.dataTransfer
      if (files.length === 0) {
        toast({
          variant: 'destructive',
          title: REFERENCE_IMAGE_ACCEPT_ERROR,
        })
        return
      }
      const file = files[0]
      if (!isImageFileCandidate(file)) {
        toast({
          variant: 'destructive',
          title: REFERENCE_IMAGE_ACCEPT_ERROR,
        })
        return
      }
      void applyFile(file)
    },
    [applyFile, isBusy, toast]
  )

  const handleClear = useCallback((): void => {
    onImageUrlChange('')
  }, [onImageUrlChange])

  const handleDragEnter = useCallback(
    (e: React.DragEvent): void => {
      e.preventDefault()
      if (!isDisabled) setDragOver(true)
    },
    [isDisabled]
  )

  const handleDragOver = useCallback(
    (e: React.DragEvent): void => {
      e.preventDefault()
      if (!isDisabled) setDragOver(true)
    },
    [isDisabled]
  )

  const handleDragLeave = useCallback((e: React.DragEvent): void => {
    if (e.currentTarget.contains(e.relatedTarget as Node)) return
    setDragOver(false)
  }, [])

  return (
    <div className="space-y-1.5" onPaste={handlePaste}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Label htmlFor={imageUrlId}>{label}</Label>
        <div className="flex items-center gap-2">
          <input
            ref={fileRef}
            id={fileInputId}
            type="file"
            accept="image/*"
            className="sr-only"
            disabled={isBusy}
            onChange={handleFileInputChange}
          />
          <Label
            htmlFor={fileInputId}
            className={cn(
              buttonVariants({ variant: 'outline', size: 'sm' }),
              'inline-flex h-8 cursor-pointer items-center gap-1.5',
              isBusy && 'pointer-events-none opacity-50'
            )}
          >
            {uploading ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
            ) : (
              <ImagePlus className="h-3.5 w-3.5" aria-hidden="true" />
            )}
            上传
          </Label>
        </div>
      </div>
      <p className="text-xs text-muted-foreground">{HELPER_TEXT}</p>
      <Input
        id={imageUrlId}
        value={imageUrl}
        onChange={(e) => {
          onImageUrlChange(e.target.value)
        }}
        placeholder="https://… 或 data:image/…;base64,…"
        disabled={isBusy}
        spellCheck={false}
        className="font-mono text-sm"
        translate="no"
      />
      <div
        className={cn('mt-2', dragOver ? 'rounded-md ring-2 ring-primary/30 ring-offset-2' : null)}
        onDragEnter={handleDragEnter}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        {hasPreview ? (
          <div className="space-y-1.5">
            <VisionImagePreview key={trimmed} src={trimmed} />
            <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
              <span>拖入新图或 Ctrl+V / ⌘V 粘贴可替换</span>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-7 px-2 text-muted-foreground"
                disabled={isBusy}
                onClick={handleClear}
              >
                <X className="mr-1 h-3.5 w-3.5" aria-hidden="true" />
                清除
              </Button>
            </div>
          </div>
        ) : (
          <EmptyDropZone uploading={uploading} disabled={isDisabled} onPickFile={openFilePicker} />
        )}
      </div>
    </div>
  )
}
