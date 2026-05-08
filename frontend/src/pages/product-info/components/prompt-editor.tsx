/**
 * PromptEditor - 带变量高亮和内联 Tooltip 的提示词编辑器
 *
 * 使用 textarea + 背景高亮层叠加 + 鼠标位置追踪：
 * - 背景层：渲染同样文本，{{param}} 处加彩色背景（文字透明，仅占位对齐）
 * - 前景 textarea：背景透明，正常编辑，高亮色从背景层透出
 * - 鼠标悬停在 {{param}} 区域时，自动弹出浮层显示中文名称 + 当前解析值
 */

import { useState, useRef, useCallback, useMemo, useEffect } from 'react'

import { cn } from '@/lib/utils'

interface PromptEditorProps {
  value: string
  onChange: (value: string) => void
  params: { key: string; label: string }[]
  resolvedValues: Record<string, unknown>
  disabled?: boolean
  rows?: number
  placeholder?: string
  className?: string
  textareaRef?: React.RefObject<HTMLTextAreaElement>
}

const PARAM_PATTERN = /(\{\{\w+\}\})/g

function renderHighlightedTokens(text: string, paramMap: Map<string, string>): React.ReactNode[] {
  if (!text) return ['\n']
  const parts = text.split(PARAM_PATTERN)
  return parts.map((part, i) => {
    const m = part.match(/^\{\{(\w+)\}\}$/)
    if (m && paramMap.has(m[1])) {
      return (
        <mark
          key={i}
          className="rounded-[3px] bg-primary/15 text-transparent"
          data-param-key={m[1]}
          data-param-label={paramMap.get(m[1])}
        >
          {part}
        </mark>
      )
    }
    return <span key={i}>{part}</span>
  })
}

function formatResolvedValue(value: unknown): string {
  if (value === null || value === undefined) return '（未设置）'
  if (typeof value === 'string') {
    if (!value) return '（空）'
    return value.length > 300 ? `${value.slice(0, 300)}…` : value
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return '（空数组）'
    const json = JSON.stringify(value)
    return json.length > 300 ? `[${String(value.length)} 项] ${json.slice(0, 300)}…` : json
  }
  if (typeof value === 'object') {
    const json = JSON.stringify(value)
    return json.length > 300 ? `${json.slice(0, 300)}…` : json
  }
  if (typeof value === 'boolean' || typeof value === 'number' || typeof value === 'bigint') {
    return String(value)
  }
  return '（无法显示）'
}

interface TooltipState {
  key: string
  label: string
  x: number
  y: number
}

export function PromptEditor({
  value,
  onChange,
  params,
  resolvedValues,
  disabled,
  rows = 14,
  placeholder,
  className,
  textareaRef: externalRef,
}: PromptEditorProps): React.JSX.Element {
  const internalRef = useRef<HTMLTextAreaElement>(null)
  const backdropRef = useRef<HTMLDivElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const taRef = externalRef ?? internalRef

  const [tooltip, setTooltip] = useState<TooltipState | null>(null)
  const hideTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const paramMap = useMemo(() => new Map(params.map((p) => [p.key, p.label])), [params])

  useEffect(
    () => () => {
      if (hideTimerRef.current) clearTimeout(hideTimerRef.current)
    },
    []
  )

  const cancelHide = useCallback(() => {
    if (hideTimerRef.current) {
      clearTimeout(hideTimerRef.current)
      hideTimerRef.current = null
    }
  }, [])

  const scheduleHide = useCallback(() => {
    cancelHide()
    hideTimerRef.current = setTimeout(() => {
      setTooltip(null)
    }, 280)
  }, [cancelHide])

  const handleScroll = useCallback(() => {
    const ta = taRef.current
    const bd = backdropRef.current
    if (ta && bd) {
      bd.scrollTop = ta.scrollTop
      bd.scrollLeft = ta.scrollLeft
    }
  }, [taRef])

  const PAD = 6

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      const container = containerRef.current
      const bd = backdropRef.current
      if (!container || !bd) return

      const marks = bd.querySelectorAll<HTMLElement>('mark[data-param-key]')
      for (const mark of marks) {
        const rect = mark.getBoundingClientRect()
        if (
          e.clientX >= rect.left - PAD &&
          e.clientX <= rect.right + PAD &&
          e.clientY >= rect.top - PAD &&
          e.clientY <= rect.bottom + PAD
        ) {
          cancelHide()
          const key = mark.dataset.paramKey ?? ''
          const label = mark.dataset.paramLabel ?? ''
          if (!key || !label) continue
          const cRect = container.getBoundingClientRect()
          setTooltip((prev) => {
            if (prev?.key === key) return prev
            return {
              key,
              label,
              x: rect.left - cRect.left,
              y: rect.bottom - cRect.top + 8,
            }
          })
          return
        }
      }
      scheduleHide()
    },
    [cancelHide, scheduleHide]
  )

  const SHARED = 'font-mono text-base leading-7 px-3 py-2 whitespace-pre-wrap break-words'

  return (
    <div
      ref={containerRef}
      className="relative"
      onMouseMove={handleMouseMove}
      onMouseLeave={scheduleHide}
    >
      {/* Backdrop: identical text, {{param}} with colored background, all text invisible */}
      <div
        ref={backdropRef}
        className={cn(
          'pointer-events-none absolute inset-0 overflow-hidden',
          'rounded-lg border-2 border-transparent',
          'max-h-[50vh] min-h-[280px]',
          'text-transparent',
          SHARED
        )}
        aria-hidden="true"
      >
        {renderHighlightedTokens(value || '', paramMap)}
        {'\n'}
      </div>

      {/* Editable textarea - transparent bg so highlight bleeds through */}
      <textarea
        ref={taRef}
        placeholder={placeholder}
        value={value}
        onChange={(e) => {
          onChange(e.target.value)
          setTooltip(null)
        }}
        onScroll={handleScroll}
        disabled={disabled}
        rows={rows}
        className={cn(
          'relative z-10 w-full resize-y',
          'rounded-lg border-2 border-muted-foreground/25 bg-transparent text-foreground shadow-sm',
          'max-h-[50vh] min-h-[280px]',
          'placeholder:text-muted-foreground',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
          'disabled:cursor-not-allowed disabled:opacity-50',
          SHARED,
          className
        )}
      />

      {/* Sticky tooltip: hoverable, delayed dismiss */}
      {tooltip && (
        <div
          className="absolute z-50 max-w-sm rounded-md border bg-popover px-3 py-2.5 text-popover-foreground shadow-lg duration-100 animate-in fade-in-0 zoom-in-95"
          style={{ left: tooltip.x, top: tooltip.y }}
          onMouseEnter={cancelHide}
          onMouseLeave={scheduleHide}
        >
          <p className="text-xs font-medium">
            {tooltip.label}
            <code className="ml-1.5 font-mono text-[11px] font-normal text-muted-foreground">
              {`{{${tooltip.key}}}`}
            </code>
          </p>
          <p className="mt-1.5 max-h-48 overflow-auto whitespace-pre-wrap break-all text-xs leading-relaxed text-muted-foreground">
            {formatResolvedValue(resolvedValues[tooltip.key])}
          </p>
        </div>
      )}
    </div>
  )
}
