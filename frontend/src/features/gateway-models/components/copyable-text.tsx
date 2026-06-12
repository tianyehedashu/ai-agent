/**
 * 点击复制；样式贴近表格单元格文本，悬停显示复制图标。
 */

import type React from 'react'

import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { useCopyToClipboard } from '@/hooks/use-copy-to-clipboard'
import { Check, Copy } from '@/lib/lucide-icons'
import { cn } from '@/lib/utils'

export interface CopyableTextProps {
  value: string
  ariaLabel?: string
  className?: string
  mono?: boolean
  /** 调用名等主字段略加重 */
  emphasis?: boolean
}

export function CopyableText({
  value,
  ariaLabel,
  className,
  mono = true,
  emphasis = false,
}: CopyableTextProps): React.JSX.Element {
  const [copy, copied] = useCopyToClipboard()

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          className={cn(
            'group/copy inline-flex max-w-full items-center gap-1 rounded-md px-1 py-0.5 text-left',
            'hover:bg-muted/70 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring/60',
            mono ? 'font-mono text-[13px] leading-snug' : 'text-sm leading-snug',
            emphasis ? 'font-medium text-foreground' : 'text-foreground/90',
            className
          )}
          aria-label={ariaLabel ?? `复制 ${value}`}
          onClick={(e) => {
            e.preventDefault()
            e.stopPropagation()
            void copy(value)
          }}
        >
          <span className="min-w-0 truncate">{value}</span>
          <span
            className={cn(
              'flex h-5 w-5 shrink-0 items-center justify-center rounded-sm text-muted-foreground transition-opacity',
              copied
                ? 'opacity-100'
                : 'opacity-0 group-hover/copy:opacity-100 group-focus-visible/copy:opacity-100'
            )}
          >
            {copied ? (
              <Check className="h-3.5 w-3.5 text-emerald-600" aria-hidden />
            ) : (
              <Copy className="h-3.5 w-3.5" aria-hidden />
            )}
          </span>
        </button>
      </TooltipTrigger>
      <TooltipContent side="top" className="max-w-md break-all text-xs">
        {copied ? '已复制' : value}
      </TooltipContent>
    </Tooltip>
  )
}
