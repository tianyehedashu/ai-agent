/**
 * 单槽重生成：参考图来源选择（各实例独立 state，避免父级 Record 触发兄弟重渲染）
 */

import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Loader2, RotateCcw } from '@/lib/lucide-icons'

import type { SlotReferenceMode } from '../hooks/use-listing-studio-image-gen'

interface SlotRegeneratePopoverProps {
  slot: number
  disabled: boolean
  isRegenerating: boolean
  onRegenerate: (slot: number, mode: SlotReferenceMode) => void
  /** compact：产出预览区角标；overlay：任务卡片 hover 层 */
  variant?: 'compact' | 'overlay'
}

export function SlotRegeneratePopover({
  slot,
  disabled,
  isRegenerating,
  onRegenerate,
  variant = 'compact',
}: SlotRegeneratePopoverProps): React.JSX.Element | null {
  const [refMode, setRefMode] = useState<SlotReferenceMode>('current')

  if (isRegenerating) {
    if (variant === 'compact') {
      return (
        <span className="flex h-7 w-7 items-center justify-center rounded-md bg-black/60">
          <Loader2 className="h-3.5 w-3.5 animate-spin text-white" />
        </span>
      )
    }
    return <Loader2 className="h-5 w-5 animate-spin text-white" />
  }

  if (variant === 'overlay') {
    return (
      <>
        <Button
          type="button"
          size="sm"
          variant="secondary"
          className="h-7 px-2 text-xs"
          disabled={disabled}
          onClick={() => {
            onRegenerate(slot, refMode)
          }}
        >
          <RotateCcw className="mr-1 h-3 w-3" />
          重生成
        </Button>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          className="h-6 px-2 text-[10px] text-white hover:bg-white/20 hover:text-white"
          disabled={disabled}
          onClick={() => {
            setRefMode((prev) => (prev === 'current' ? 'source' : 'current'))
          }}
        >
          {refMode === 'current' ? '参考：当前图' : '参考：生图参考图'}
        </Button>
      </>
    )
  }

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          type="button"
          size="icon"
          variant="secondary"
          className="h-7 w-7 rounded-md shadow-sm"
          disabled={disabled}
          aria-label={`重新生成第 ${String(slot)} 张`}
        >
          <RotateCcw className="h-3.5 w-3.5" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-48 p-2" align="end">
        <p className="mb-2 text-xs text-muted-foreground">参考图来源</p>
        <div className="flex flex-col gap-1">
          <Button
            type="button"
            size="sm"
            variant={refMode === 'current' ? 'default' : 'ghost'}
            className="h-8 justify-start text-xs"
            onClick={() => {
              setRefMode('current')
            }}
          >
            当前图
          </Button>
          <Button
            type="button"
            size="sm"
            variant={refMode === 'source' ? 'default' : 'ghost'}
            className="h-8 justify-start text-xs"
            onClick={() => {
              setRefMode('source')
            }}
          >
            生图参考图
          </Button>
          <Button
            type="button"
            size="sm"
            className="mt-1 h-8 text-xs"
            disabled={disabled}
            onClick={() => {
              onRegenerate(slot, refMode)
            }}
          >
            开始重生成
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  )
}
