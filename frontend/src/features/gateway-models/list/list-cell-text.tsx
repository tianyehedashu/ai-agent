/**
 * 表格单元格：截断显示 + Tooltip 展示全文。
 */

import type React from 'react'

import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'

export interface ListCellTextProps {
  value: string
  /** Tooltip 全文；缺省与 value 相同 */
  tooltip?: string
  className?: string
  mono?: boolean
}

export function ListCellText({
  value,
  tooltip,
  className,
  mono = false,
}: ListCellTextProps): React.JSX.Element {
  const tip = tooltip ?? value
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          className={cn(
            'block min-w-0 truncate',
            mono ? 'font-mono text-[13px] text-foreground/90' : 'text-sm text-foreground',
            className
          )}
        >
          {value}
        </span>
      </TooltipTrigger>
      <TooltipContent side="top" className="max-w-md break-all text-xs">
        {tip}
      </TooltipContent>
    </Tooltip>
  )
}
