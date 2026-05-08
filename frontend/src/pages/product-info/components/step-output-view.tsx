/**
 * 步骤输出展示：中间文案、图片、生成的提示词，支持查看与复制
 * - 图片分析（image_descriptions）：解析 description 内 markdown JSON，卡片展示
 * - 竞品/商品链接分析（competitor_info、product_info）：解析 raw_text 内 markdown JSON，卡片展示
 */

import { useState } from 'react'

import { Copy, Check, ChevronDown, ChevronRight } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { ImageLightbox } from '@/components/ui/image-lightbox'
import { useCopyToClipboard, useCopyToClipboardKeyed } from '@/hooks/use-copy-to-clipboard'
import { useProductInfoCapabilities } from '@/hooks/use-product-info-capabilities'
import { cn } from '@/lib/utils'
import type { ProductInfoJobStep } from '@/types/product-info'

interface StepOutputViewProps {
  step: ProductInfoJobStep
  defaultExpanded?: boolean
  className?: string
}

/** 从可能被 ```json ... ``` 包裹的字符串中解析出 JSON（对象或数组），失败返回 null */
function extractJson(description: string): Record<string, unknown> | unknown[] | null {
  if (!description || typeof description !== 'string') return null
  let raw = description.trim()
  const codeBlock = raw.match(/^```(?:json)?\s*([\s\S]*?)```$/m)
  if (codeBlock) raw = codeBlock[1].trim()
  try {
    const parsed = JSON.parse(raw) as unknown
    if (parsed && typeof parsed === 'object') return parsed as Record<string, unknown> | unknown[]
    return null
  } catch {
    return null
  }
}

/** 提取 JSON 对象（仅 dict，兼容旧调用） */
function extractJsonObject(description: string): Record<string, unknown> | null {
  const result = extractJson(description)
  return result && !Array.isArray(result) ? result : null
}

/** 图片分析结果字段中文标签（兼容常见 LLM 返回 key：如通义 VL 的 main_colors、key_components、image_prompt_en 等） */
const IMAGE_ANALYSIS_FIELD_LABELS: Record<string, string> = {
  product_type: '产品类型',
  product_name: '产品名称',
  colors: '颜色',
  main_colors: '主要颜色',
  color_scheme: '配色方案',
  materials: '材质',
  material: '材质',
  estimated_size: '预估尺寸',
  estimated_dimensions: '预估尺寸',
  shape_outline: '形状轮廓',
  surface_process: '表面工艺',
  surface_finish: '表面工艺',
  design_style: '设计风格',
  important_parts: '重要部件',
  key_components: '重要部件',
  main_functions: '主要功能',
  primary_functions: '主要功能',
  selling_points: '卖点',
  usage_scenarios: '使用场景',
  regeneration_prompts: '生图提示词',
  image_prompt_en: '生图提示词（英文）',
  image_prompt_cn: '生图提示词（中文）',
}

function formatScalarForDisplay(value: unknown): string {
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean' || typeof value === 'bigint') {
    return String(value)
  }
  return JSON.stringify(value)
}

function extractImageUrls(obj: unknown): string[] {
  if (!obj || typeof obj !== 'object') return []
  const urls: string[] = []
  const walk = (o: unknown): void => {
    if (Array.isArray(o)) {
      o.forEach((item) => {
        if (typeof item === 'string' && (item.startsWith('http://') || item.startsWith('https://')))
          urls.push(item)
        else if (item && typeof item === 'object') walk(item)
      })
      return
    }
    if (typeof o === 'object' && o !== null) {
      const v = (o as Record<string, unknown>).url
      if (typeof v === 'string' && (v.startsWith('http') || v.startsWith('//'))) urls.push(v)
      Object.values(o).forEach(walk)
    }
  }
  walk(obj)
  return urls
}

function JsonBlock({ data, label }: { data: unknown; label?: string }): React.JSX.Element {
  const [copy, copied] = useCopyToClipboard()
  const text = typeof data === 'string' ? data : JSON.stringify(data, null, 2)
  return (
    <div className="relative">
      {label && <p className="mb-1.5 text-sm font-medium text-muted-foreground">{label}</p>}
      <pre className="max-h-80 overflow-auto rounded-lg border border-border/60 bg-muted/30 p-4 text-sm leading-relaxed">
        {text}
      </pre>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className="absolute right-2 top-2"
        onClick={() => copy(text)}
      >
        {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
      </Button>
    </div>
  )
}

function ImageGrid({ urls }: { urls: string[] }): React.JSX.Element {
  const [lightbox, setLightbox] = useState<string | null>(null)
  if (urls.length === 0) return <></>
  return (
    <>
      <p className="mb-1.5 text-sm font-medium text-muted-foreground">图片</p>
      <div className="flex flex-wrap gap-2.5">
        {urls.map((url, i) => (
          <button
            key={`${url}-${String(i)}`}
            type="button"
            className="h-24 w-24 overflow-hidden rounded-lg border border-border/60 bg-muted transition-transform hover:scale-[1.02]"
            onClick={() => {
              setLightbox(url)
            }}
          >
            <img
              src={url}
              alt=""
              className="h-full w-full object-cover"
              referrerPolicy="no-referrer"
            />
          </button>
        ))}
      </div>
      <ImageLightbox
        src={lightbox}
        onClose={() => {
          setLightbox(null)
        }}
      />
    </>
  )
}

function PromptsList({ prompts }: { prompts: string[] }): React.JSX.Element {
  const [copy, copiedKey] = useCopyToClipboardKeyed()
  const list = (prompts.length ? prompts : Array.from({ length: 8 }, () => '')).slice(0, 8)
  return (
    <div className="space-y-2.5">
      <p className="text-sm font-medium text-muted-foreground">8 图提示词</p>
      {list.map((p, i) => (
        <div
          key={String(i)}
          className="flex items-start gap-2.5 rounded-lg border border-border/60 bg-muted/30 p-3"
        >
          <span className="shrink-0 text-sm font-medium text-muted-foreground">
            {i === 0 ? '第1张（白底）' : `第${String(i + 1)}张`}
          </span>
          <p className="min-w-0 flex-1 text-sm">{p || '—'}</p>
          <Button type="button" variant="ghost" size="sm" onClick={() => copy(p || '', i)}>
            {copiedKey === i ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
          </Button>
        </div>
      ))}
    </div>
  )
}

/** 图片分析结果：解析 image_descriptions 中的 description（含 ```json```），以卡片形式展示 */
function ImageAnalysisResult({
  items,
  raw,
}: {
  items: Array<{ description?: string }>
  raw?: string
}): React.JSX.Element {
  const [copy, copiedIndex] = useCopyToClipboardKeyed()
  const [showRaw, setShowRaw] = useState<number | null>(null)

  if (!Array.isArray(items) || items.length === 0) {
    if (raw?.trim()) {
      return (
        <div className="space-y-2">
          <p className="text-sm font-medium text-muted-foreground">解析结果</p>
          <p className="whitespace-pre-wrap break-words rounded-lg border border-border/60 bg-muted/30 p-3 text-sm leading-relaxed">
            {raw}
          </p>
        </div>
      )
    }
    return (
      <p className="text-sm text-muted-foreground">
        暂无解析结果。请检查图片链接是否可访问、或更换视觉模型后重试。
      </p>
    )
  }

  return (
    <div className="space-y-6">
      <p className="text-sm font-medium text-muted-foreground">解析结果</p>
      {items.map((item, index) => {
        const desc = (item.description ?? '').trim()
        const parsed = extractJsonObject(desc)
        const label = items.length > 1 ? `第 ${String(index + 1)} 张图` : undefined
        const fallbackText = !desc && raw ? raw : desc

        return (
          <div
            key={String(index)}
            className="overflow-hidden rounded-xl border border-border/60 bg-card shadow-sm"
          >
            {label && (
              <div className="border-b border-border/40 bg-muted/30 px-4 py-2 text-sm font-medium">
                {label}
              </div>
            )}
            <div className="space-y-4 p-4">
              {parsed ? (
                <>
                  <div className="grid gap-3 sm:grid-cols-1">
                    {Object.entries(parsed).map(([key, value]) => {
                      const fieldLabel = IMAGE_ANALYSIS_FIELD_LABELS[key] ?? key
                      if (value === null || value === undefined || value === '') return null
                      if (typeof value === 'object' && !Array.isArray(value)) {
                        return (
                          <div
                            key={key}
                            className="rounded-lg border border-border/40 bg-muted/20 p-3"
                          >
                            <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                              {fieldLabel}
                            </p>
                            <StructuredFieldValue value={value} />
                          </div>
                        )
                      }
                      if (Array.isArray(value)) {
                        const arrFiltered = value.filter(
                          (v) => v !== null && v !== undefined && v !== ''
                        )
                        if (arrFiltered.length === 0) return null
                        return (
                          <div
                            key={key}
                            className="flex flex-col gap-1.5 rounded-lg border border-border/40 bg-muted/20 p-3"
                          >
                            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                              {fieldLabel}
                            </p>
                            <StructuredFieldValue value={arrFiltered} />
                          </div>
                        )
                      }
                      return (
                        <div
                          key={key}
                          className="flex flex-col gap-1 rounded-lg border border-border/40 bg-muted/20 p-3"
                        >
                          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                            {fieldLabel}
                          </p>
                          <p className="whitespace-pre-wrap break-words text-sm leading-relaxed">
                            {typeof value === 'string' ? value : formatScalarForDisplay(value)}
                          </p>
                        </div>
                      )
                    })}
                  </div>
                  <div className="flex items-center gap-2 border-t border-border/40 pt-2">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="h-8 text-xs"
                      onClick={() => {
                        setShowRaw(showRaw === index ? null : index)
                      }}
                    >
                      {showRaw === index ? '收起原始 JSON' : '查看原始 JSON'}
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="h-8 text-xs"
                      onClick={() => copy(desc, index)}
                    >
                      {copiedIndex === index ? (
                        <Check className="h-3.5 w-3.5" />
                      ) : (
                        <Copy className="h-3.5 w-3.5" />
                      )}
                      <span className="ml-1">复制</span>
                    </Button>
                  </div>
                  {showRaw === index && (
                    <pre className="max-h-60 overflow-auto rounded-lg border border-border/60 bg-muted/30 p-3 text-xs leading-relaxed">
                      {desc}
                    </pre>
                  )}
                </>
              ) : (
                <>
                  {fallbackText ? (
                    <p className="whitespace-pre-wrap break-words text-sm leading-relaxed">
                      {fallbackText}
                    </p>
                  ) : (
                    <p className="text-sm text-muted-foreground">
                      本张图无解析内容。请检查图片链接是否可访问或更换模型重试。
                    </p>
                  )}
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-8 text-xs"
                    onClick={() => copy(desc !== '' ? desc : (raw ?? ''), index)}
                  >
                    {copiedIndex === index ? (
                      <Check className="h-3.5 w-3.5" />
                    ) : (
                      <Copy className="h-3.5 w-3.5" />
                    )}
                    <span className="ml-1">复制</span>
                  </Button>
                </>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}

/** 渲染单个字段值：字符串、数组（含对象元素）、嵌套对象，递归处理任意深度 */
function StructuredFieldValue({ value }: { value: unknown }): React.JSX.Element {
  if (value === null || value === undefined || value === '') return <></>
  if (typeof value === 'string') {
    return <p className="whitespace-pre-wrap break-words text-sm leading-relaxed">{value}</p>
  }
  if (Array.isArray(value)) {
    const filtered = value.filter((v) => v !== null && v !== undefined && v !== '')
    if (filtered.length === 0) return <></>
    const hasComplex = filtered.some((v) => typeof v === 'object')
    if (hasComplex) {
      return (
        <div className="space-y-2">
          {filtered.map((item, i) => (
            <div key={String(i)} className="rounded-md border border-border/30 bg-muted/10 p-2.5">
              <StructuredFieldValue value={item as unknown} />
            </div>
          ))}
        </div>
      )
    }
    return (
      <ul className="space-y-1.5">
        {filtered.map((item, i) => (
          <li key={String(i)} className="flex gap-2 text-sm leading-relaxed">
            <span className="shrink-0 text-muted-foreground">•</span>
            <span className="whitespace-pre-wrap break-words">{String(item)}</span>
          </li>
        ))}
      </ul>
    )
  }
  if (typeof value === 'object') {
    const obj = value as Record<string, unknown>
    return (
      <div className="space-y-2 rounded-md border border-border/30 bg-muted/10 p-3">
        {Object.entries(obj).map(([k, v]) =>
          v !== null && v !== undefined && v !== '' ? (
            <div key={k} className="flex flex-col gap-1">
              <span className="text-xs font-medium text-muted-foreground">{k}</span>
              <StructuredFieldValue value={v} />
            </div>
          ) : null
        )}
      </div>
    )
  }
  return <p className="text-sm">{formatScalarForDisplay(value)}</p>
}

/** raw_text 降级输出：解析 raw_text 内的 JSON（dict 或 array），卡片展示 */
function ParsedRawTextCard({ data }: { data: { raw_text: string } }): React.JSX.Element {
  const [copy, copied] = useCopyToClipboard()
  const [showRaw, setShowRaw] = useState(false)
  const rawText = data.raw_text
  const parsed = extractJson(rawText)

  if (!rawText) {
    return <p className="text-sm text-muted-foreground">暂无内容</p>
  }

  const renderParsedContent = (): React.ReactNode | null => {
    if (!parsed) return null
    if (Array.isArray(parsed)) {
      return <StructuredFieldValue value={parsed} />
    }
    const entries = Object.entries(parsed).filter(
      ([, v]) => v !== null && v !== undefined && v !== ''
    )
    if (entries.length === 0) return null
    return (
      <div className="grid gap-3 sm:grid-cols-1">
        {entries.map(([key, value]) => (
          <div
            key={key}
            className="flex flex-col gap-1.5 rounded-lg border border-border/40 bg-muted/20 p-3"
          >
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              {key}
            </p>
            <StructuredFieldValue value={value} />
          </div>
        ))}
      </div>
    )
  }

  const parsedContent = renderParsedContent()

  return (
    <div className="space-y-4">
      {parsedContent ? (
        <>
          {parsedContent}
          <div className="flex items-center gap-2 border-t border-border/40 pt-3">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-8 text-xs"
              onClick={() => {
                setShowRaw((v) => !v)
              }}
            >
              {showRaw ? '收起原始 JSON' : '查看原始 JSON'}
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-8 text-xs"
              onClick={() => copy(rawText)}
            >
              {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
              <span className="ml-1">复制</span>
            </Button>
          </div>
          {showRaw && (
            <pre className="max-h-60 overflow-auto rounded-lg border border-border/60 bg-muted/30 p-3 text-xs leading-relaxed">
              {rawText}
            </pre>
          )}
        </>
      ) : (
        <>
          <p className="whitespace-pre-wrap break-words text-sm leading-relaxed">{rawText}</p>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-8 text-xs"
            onClick={() => copy(rawText)}
          >
            {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
            <span className="ml-1">复制</span>
          </Button>
        </>
      )}
    </div>
  )
}

/** 判断输出是否为 JSON 解析失败的降级格式 { raw_text: string }（仅含 raw_text 一个字段） */
function isRawTextOutput(mainData: unknown): boolean {
  if (
    mainData === null ||
    mainData === undefined ||
    typeof mainData !== 'object' ||
    Array.isArray(mainData)
  ) {
    return false
  }
  const obj = mainData as Record<string, unknown>
  return typeof obj.raw_text === 'string' && Object.keys(obj).length === 1
}

/** 结构化输出卡片：将 dict 或 array 以卡片展示，附带复制和原始 JSON 查看 */
function StructuredOutputCard({ data }: { data: unknown }): React.JSX.Element {
  const [copy, copied] = useCopyToClipboard()
  const [showRaw, setShowRaw] = useState(false)
  const rawJson = JSON.stringify(data, null, 2)

  const renderContent = (): React.ReactNode | null => {
    if (Array.isArray(data)) {
      const filtered = data.filter((v) => v !== null && v !== undefined && v !== '')
      if (filtered.length === 0) return null
      return <StructuredFieldValue value={filtered} />
    }
    if (typeof data === 'object' && data !== null) {
      const entries = Object.entries(data as Record<string, unknown>).filter(
        ([, v]) => v !== null && v !== undefined && v !== ''
      )
      if (entries.length === 0) return null
      return (
        <div className="grid gap-3 sm:grid-cols-1">
          {entries.map(([key, value]) => (
            <div
              key={key}
              className="flex flex-col gap-1.5 rounded-lg border border-border/40 bg-muted/20 p-3"
            >
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                {key}
              </p>
              <StructuredFieldValue value={value} />
            </div>
          ))}
        </div>
      )
    }
    return null
  }

  const content = renderContent()
  if (!content) return <JsonBlock data={data} />

  return (
    <div className="space-y-4">
      {content}
      <div className="flex items-center gap-2 border-t border-border/40 pt-3">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-8 text-xs"
          onClick={() => {
            setShowRaw((v) => !v)
          }}
        >
          {showRaw ? '收起原始 JSON' : '查看原始 JSON'}
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-8 text-xs"
          onClick={() => copy(rawJson)}
        >
          {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
          <span className="ml-1">复制</span>
        </Button>
      </div>
      {showRaw && (
        <pre className="max-h-60 overflow-auto rounded-lg border border-border/60 bg-muted/30 p-3 text-xs leading-relaxed">
          {rawJson}
        </pre>
      )}
    </div>
  )
}

export function StepOutputView({
  step,
  defaultExpanded = true,
  className,
}: StepOutputViewProps): React.JSX.Element {
  const caps = useProductInfoCapabilities()
  const [expanded, setExpanded] = useState(defaultExpanded)
  const out = step.output_snapshot ?? {}
  const capId = step.capability_id
  const mainKey = caps.outputKeys[capId]
  const mainData = mainKey ? out[mainKey] : null
  const imageUrls = extractImageUrls(out)
  const inputUrls = extractImageUrls(step.input_snapshot ?? {})

  const hasContent =
    (mainData !== null && mainData !== undefined) || imageUrls.length > 0 || inputUrls.length > 0

  return (
    <div
      className={cn(
        'overflow-hidden rounded-xl border border-border/60 bg-muted/20 transition-shadow',
        expanded && 'ring-1 ring-primary/10',
        className
      )}
    >
      <button
        type="button"
        className="flex w-full items-center gap-3 px-4 py-3.5 text-left transition-colors hover:bg-muted/50 focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        onClick={() => {
          setExpanded((e) => !e)
        }}
      >
        {expanded ? (
          <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
        )}
        <span className="text-sm font-medium tracking-tight">
          {caps.capabilityNames[capId] ?? capId}
          {step.status === 'completed' && (
            <span className="font-normal text-muted-foreground"> · 已完成</span>
          )}
          {step.status === 'failed' && (
            <span className="font-normal text-destructive"> · 失败</span>
          )}
        </span>
        {step.error_message && (
          <span className="truncate text-sm text-destructive">{step.error_message}</span>
        )}
      </button>
      {expanded && (
        <div className="border-t border-border/60 bg-card/50 px-5 pb-5 pt-4">
          {step.error_message && (
            <p className="mb-3 text-sm text-destructive">{step.error_message}</p>
          )}
          {!hasContent && step.status !== 'failed' && (
            <p className="text-sm text-muted-foreground">暂无输出</p>
          )}
          {inputUrls.length > 0 && (
            <div className="mb-4">
              <p className="mb-1.5 text-sm font-medium text-muted-foreground">输入图片</p>
              <div className="flex flex-wrap gap-2.5">
                {inputUrls.map((url, i) => (
                  <a
                    key={`in-${String(i)}`}
                    href={url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block h-20 w-20 overflow-hidden rounded-lg border border-border"
                  >
                    <img
                      src={url}
                      alt=""
                      className="h-full w-full object-cover"
                      referrerPolicy="no-referrer"
                    />
                  </a>
                ))}
              </div>
            </div>
          )}
          {mainKey === 'prompts' && Array.isArray(mainData) && (
            <PromptsList prompts={mainData.map(String)} />
          )}
          {mainKey === 'image_descriptions' && Array.isArray(mainData) && (
            <div className="mb-4">
              <ImageAnalysisResult
                items={mainData as Array<{ description?: string }>}
                raw={typeof out.raw === 'string' ? out.raw : undefined}
              />
            </div>
          )}
          {isRawTextOutput(mainData) && (
            <div className="mb-4">
              <ParsedRawTextCard data={mainData as { raw_text: string }} />
            </div>
          )}
          {mainData !== null &&
            mainData !== undefined &&
            mainKey !== 'prompts' &&
            mainKey !== 'image_descriptions' &&
            !isRawTextOutput(mainData) && (
              <div className="mb-4">
                {typeof mainData === 'object' ? (
                  <StructuredOutputCard data={mainData} />
                ) : (
                  <JsonBlock data={mainData} />
                )}
              </div>
            )}
          {imageUrls.length > 0 && (
            <div className="mt-3">
              <ImageGrid urls={imageUrls} />
            </div>
          )}
          {step.prompt_used && (
            <details className="mt-3">
              <summary className="cursor-pointer text-sm text-muted-foreground">
                使用的提示词
              </summary>
              <pre className="mt-1.5 max-h-40 overflow-auto rounded-lg border border-border/60 p-3 text-sm leading-relaxed text-muted-foreground">
                {step.prompt_used}
              </pre>
            </details>
          )}
        </div>
      )}
    </div>
  )
}
