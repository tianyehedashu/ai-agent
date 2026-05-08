/**
 * 分类输入区：产品链接、竞品链接、产品名称、关键词、图片上传
 */

import { useState, useRef } from 'react'

import { ImagePlus, X, Loader2, Link2, Package, Tags, ImageIcon } from 'lucide-react'

import { productInfoApi } from '@/api/productInfo'
import { Button } from '@/components/ui/button'
import { ImageLightbox } from '@/components/ui/image-lightbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { INPUT_FIELDS, INPUT_IMAGE_URLS_KEY } from '@/constants/product-info'
import { useToast } from '@/hooks/use-toast'

import { type ProductInfoInputs, FIELD_ICONS } from './input-panel-shared'

/** 图片 URL 列表编辑：显示缩略图、添加链接、删除、点击预览。供 InputPanel 与 StepContextPanel 复用 */
export function ImageUrlListEditor({
  urls,
  onChange,
  disabled,
  compact,
  label = '参考图片',
  /** 为 false 时仅渲染缩略图与灯箱（链接输入由外部并列展示时使用） */
  showLinkInput = true,
}: {
  urls: string[]
  onChange: (urls: string[]) => void
  disabled?: boolean
  compact?: boolean
  label?: string
  showLinkInput?: boolean
}): React.JSX.Element {
  const [linkInput, setLinkInput] = useState('')
  const [lightboxUrl, setLightboxUrl] = useState<string | null>(null)
  const { toast } = useToast()

  const addLink = (): void => {
    const trimmed = linkInput.trim()
    if (!trimmed) return
    if (!/^https?:\/\//i.test(trimmed)) {
      toast({ title: '请输入有效的图片链接（以 http 或 https 开头）', variant: 'destructive' })
      return
    }
    onChange([...urls, trimmed])
    setLinkInput('')
  }

  const remove = (index: number): void => {
    onChange(urls.filter((_, i) => i !== index))
  }

  return (
    <div className={compact ? 'space-y-2.5' : 'space-y-3'}>
      {label ? (
        <Label className="flex items-center gap-1.5 text-sm font-medium text-muted-foreground">
          <ImageIcon className="h-3.5 w-3.5" />
          {label}
        </Label>
      ) : null}
      {showLinkInput && (
        <div className="flex flex-wrap gap-2">
          <Input
            placeholder="https://... 输入图片链接"
            value={linkInput}
            onChange={(e) => {
              setLinkInput(e.target.value)
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault()
                addLink()
              }
            }}
            disabled={disabled}
            className="h-9 min-w-[160px] max-w-[280px] flex-1 rounded-md border-border/60 text-sm"
          />
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-9 rounded-md"
            onClick={addLink}
            disabled={(disabled ?? false) || !linkInput.trim()}
          >
            <Link2 className="h-3.5 w-3.5" />
            <span className="ml-1.5">添加链接</span>
          </Button>
        </div>
      )}
      {urls.length > 0 && (
        <div className="flex flex-wrap gap-3">
          {urls.map((url, i) => (
            <div
              key={`${url}-${String(i)}`}
              className="flex flex-col gap-1.5 rounded-xl border border-border/50 bg-muted/30 p-2 shadow-sm"
            >
              <div className="relative h-24 w-24 overflow-hidden rounded-lg">
                <button
                  type="button"
                  className="absolute inset-0 flex h-full w-full items-center justify-center focus:outline-none focus:ring-2 focus:ring-primary"
                  onClick={() => {
                    setLightboxUrl(url)
                  }}
                  disabled={disabled}
                  aria-label="预览"
                >
                  <img
                    src={url}
                    alt=""
                    className="h-full w-full object-cover"
                    referrerPolicy="no-referrer"
                  />
                </button>
                <button
                  type="button"
                  className="absolute right-0 top-0 rounded-bl-lg bg-black/60 p-1 text-white transition-colors hover:bg-black/80"
                  onClick={(e) => {
                    e.stopPropagation()
                    remove(i)
                  }}
                  disabled={disabled}
                  aria-label="删除"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
              <a
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                className="max-w-[160px] truncate text-xs text-muted-foreground underline underline-offset-2 hover:text-foreground"
                title={url}
              >
                {url}
              </a>
            </div>
          ))}
        </div>
      )}
      <ImageLightbox
        src={lightboxUrl}
        onClose={() => {
          setLightboxUrl(null)
        }}
      />
    </div>
  )
}

export function FieldRow({
  fieldKey,
  label,
  placeholder,
  value,
  onChange,
  disabled,
  icon: Icon,
}: {
  fieldKey: string
  label: string
  placeholder: string
  value: string
  onChange: (v: string) => void
  disabled?: boolean
  icon: React.ComponentType<{ className?: string }>
}): React.JSX.Element {
  return (
    <div className="space-y-1.5">
      <Label
        htmlFor={fieldKey}
        className="flex items-center gap-1.5 text-sm font-medium text-muted-foreground"
      >
        <Icon className="h-3.5 w-3.5" />
        {label}
      </Label>
      <Input
        id={fieldKey}
        placeholder={placeholder}
        value={value}
        onChange={(e) => {
          onChange(e.target.value)
        }}
        disabled={disabled}
        className="h-9 rounded-md border-border/60 bg-background/80 text-sm"
      />
    </div>
  )
}

interface InputPanelProps {
  inputs: ProductInfoInputs
  onChange: (inputs: ProductInfoInputs) => void
  disabled?: boolean
  /** 侧栏紧凑模式：单列、更小间距 */
  compact?: boolean
}

export function InputPanel({
  inputs,
  onChange,
  disabled,
  compact,
}: InputPanelProps): React.JSX.Element {
  const [uploading, setUploading] = useState(false)
  const [linkInput, setLinkInput] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)
  const { toast } = useToast()

  const imageUrls = inputs[INPUT_IMAGE_URLS_KEY] ?? []

  const addImageLink = (): void => {
    const trimmed = linkInput.trim()
    if (!trimmed) return
    if (!/^https?:\/\//i.test(trimmed)) {
      toast({ title: '请输入有效的图片链接（以 http 或 https 开头）', variant: 'destructive' })
      return
    }
    update(INPUT_IMAGE_URLS_KEY, [...imageUrls, trimmed])
    setLinkInput('')
  }

  const update = (key: string, value: string | string[] | undefined): void => {
    onChange({ ...inputs, [key]: value })
  }

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>): Promise<void> => {
    const file = e.target.files?.[0]
    if (!file) return
    if (!file.type.startsWith('image/')) {
      toast({ title: '请选择图片文件', variant: 'destructive' })
      return
    }
    setUploading(true)
    try {
      const res = await productInfoApi.upload(file)
      update(INPUT_IMAGE_URLS_KEY, [...imageUrls, res.url])
      toast({ title: '上传成功' })
    } catch (err) {
      toast({ title: '上传失败', description: String(err), variant: 'destructive' })
    } finally {
      setUploading(false)
      e.target.value = ''
    }
  }

  const productFields = INPUT_FIELDS.filter(
    (f) => f.key === 'product_link' || f.key === 'product_name'
  )
  const otherFields = INPUT_FIELDS.filter(
    (f) => f.key === 'competitor_link' || f.key === 'keywords'
  )
  const allFields = compact ? INPUT_FIELDS : null
  const showTwoCol = !compact

  return (
    <div className={compact ? 'space-y-4' : 'space-y-6'}>
      {showTwoCol ? (
        <div className="grid gap-5 sm:grid-cols-2">
          <div className="space-y-4">
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              产品信息
            </p>
            <div className="space-y-3">
              {productFields.map(({ key, label, placeholder }) => (
                <FieldRow
                  key={key}
                  fieldKey={key}
                  label={label}
                  placeholder={placeholder}
                  value={(inputs as Record<string, string>)[key] ?? ''}
                  onChange={(v) => {
                    update(key, v === '' ? undefined : v)
                  }}
                  disabled={disabled}
                  icon={FIELD_ICONS[key] ?? Package}
                />
              ))}
            </div>
          </div>
          <div className="space-y-4">
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              竞品与关键词
            </p>
            <div className="space-y-3">
              {otherFields.map(({ key, label, placeholder }) => (
                <FieldRow
                  key={key}
                  fieldKey={key}
                  label={label}
                  placeholder={placeholder}
                  value={(inputs as Record<string, string>)[key] ?? ''}
                  onChange={(v) => {
                    update(key, v === '' ? undefined : v)
                  }}
                  disabled={disabled}
                  icon={FIELD_ICONS[key] ?? Tags}
                />
              ))}
            </div>
          </div>
        </div>
      ) : (
        <div className="space-y-3.5">
          {allFields?.map(({ key, label, placeholder }) => (
            <FieldRow
              key={key}
              fieldKey={key}
              label={label}
              placeholder={placeholder}
              value={(inputs as Record<string, string>)[key] ?? ''}
              onChange={(v) => {
                update(key, v === '' ? undefined : v)
              }}
              disabled={disabled}
              icon={FIELD_ICONS[key] ?? Package}
            />
          ))}
        </div>
      )}

      <div
        className={
          compact
            ? 'space-y-2.5 border-t border-border/40 pt-4'
            : 'space-y-3 border-t border-border/40 pt-5'
        }
      >
        <Label className="flex items-center gap-1.5 text-sm font-medium text-muted-foreground">
          <ImageIcon className="h-3.5 w-3.5" />
          参考图片
        </Label>
        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={handleUpload}
          disabled={(disabled ?? false) || uploading}
        />
        <div className="flex flex-wrap items-stretch gap-3">
          <div className={imageUrls.length === 0 ? 'min-w-[120px] flex-1' : ''}>
            {imageUrls.length === 0 ? (
              <button
                type="button"
                className={`flex w-full flex-col items-center justify-center gap-2 rounded-md border border-dashed border-border/60 bg-muted/20 text-center transition-colors hover:border-primary/40 hover:bg-muted/40 disabled:pointer-events-none disabled:opacity-50 ${compact ? 'py-4' : 'py-6'}`}
                onClick={() => fileRef.current?.click()}
                disabled={(disabled ?? false) || uploading}
              >
                {uploading ? (
                  <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                ) : (
                  <ImagePlus
                    className={`text-muted-foreground ${compact ? 'h-6 w-6' : 'h-8 w-8'}`}
                  />
                )}
                <span className="text-sm text-muted-foreground">点击上传</span>
              </button>
            ) : (
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-9 rounded-md"
                onClick={() => fileRef.current?.click()}
                disabled={(disabled ?? false) || uploading}
              >
                {uploading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <ImagePlus className="h-4 w-4" />
                )}
                <span className="ml-1.5">上传</span>
              </Button>
            )}
          </div>
          <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2">
            <Input
              placeholder="https://... 输入图片链接"
              value={linkInput}
              onChange={(e) => {
                setLinkInput(e.target.value)
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault()
                  addImageLink()
                }
              }}
              disabled={disabled}
              className="h-9 min-w-[140px] max-w-[240px] flex-1 rounded-md border-border/60 text-sm"
            />
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-9 shrink-0 rounded-md"
              onClick={addImageLink}
              disabled={(disabled ?? false) || !linkInput.trim()}
            >
              <Link2 className="h-3.5 w-3.5" />
              <span className="ml-1.5">添加链接</span>
            </Button>
          </div>
        </div>
        {imageUrls.length > 0 && (
          <p className="text-sm text-muted-foreground">点击缩略图可全屏预览</p>
        )}
        <ImageUrlListEditor
          urls={imageUrls}
          onChange={(urls) => {
            update(INPUT_IMAGE_URLS_KEY, urls.length ? urls : undefined)
          }}
          disabled={disabled}
          compact={compact}
          label=""
          showLinkInput={false}
        />
      </div>
    </div>
  )
}
