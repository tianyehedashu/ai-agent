/**
 * PromptOptimizeDialog - 视频提示词优化系统提示词编辑对话框
 *
 * 支持：
 * - 首次打开加载后端默认模板
 * - 编辑后持久化保存（Zustand persist，按用户隔离）
 * - 恢复默认（清除自定义并回到后端默认模板）
 */

import { useState, useEffect, useCallback, useRef } from 'react'

import { useQuery } from '@tanstack/react-query'
import { RotateCcw, Loader2 } from 'lucide-react'

import { videoTaskApi } from '@/api/videoTask'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

interface PromptOptimizeDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** 当前生效的系统提示词（可能是用户自定义的，也可能是空 = 默认） */
  value: string
  /** 保存回调：传入自定义值，空字符串表示恢复默认 */
  onChange: (value: string) => void
}

export function PromptOptimizeDialog({
  open,
  onOpenChange,
  value,
  onChange,
}: PromptOptimizeDialogProps): React.JSX.Element {
  const [draft, setDraft] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const { data: templateData, isLoading: isLoadingTemplate } = useQuery({
    queryKey: ['video-prompt-template'],
    queryFn: () => videoTaskApi.getPromptTemplate(),
    staleTime: Infinity,
  })

  const defaultPrompt = templateData?.systemPrompt ?? ''

  const effectiveDisplay = useCallback((v: string) => v || defaultPrompt, [defaultPrompt])

  useEffect(() => {
    if (open) {
      setDraft(effectiveDisplay(value))
      requestAnimationFrame(() => {
        textareaRef.current?.focus()
      })
    }
  }, [open, value, effectiveDisplay])

  const handleSave = (): void => {
    const trimmed = draft.trim()
    if (trimmed === defaultPrompt.trim()) {
      onChange('')
    } else {
      onChange(trimmed)
    }
    onOpenChange(false)
  }

  const handleReset = (): void => {
    setDraft(defaultPrompt)
  }

  const handleKeyDown = (e: React.KeyboardEvent): void => {
    if (e.key === 's' && (e.metaKey || e.ctrlKey)) {
      e.preventDefault()
      handleSave()
    }
  }

  const isModified = draft.trim() !== '' && draft.trim() !== defaultPrompt.trim()
  const charCount = draft.length

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="flex max-h-[90vh] max-w-3xl flex-col gap-0 p-0"
        onKeyDown={handleKeyDown}
      >
        {/* 固定头部 */}
        <DialogHeader className="flex-none border-b px-6 py-4">
          <DialogTitle className="flex items-center gap-2">
            提示词优化 - 系统指令
            {isModified && (
              <span className="inline-block rounded-full bg-primary/10 px-2 py-0.5 text-xs font-normal text-primary">
                已自定义
              </span>
            )}
          </DialogTitle>
          <DialogDescription>
            编辑用于生成视频提示词的系统指令。此指令告诉 AI 如何根据你的输入生成视频提示词。
          </DialogDescription>
        </DialogHeader>

        {/* 可滚动编辑区 */}
        <div className="flex-1 overflow-hidden px-6 py-4">
          {isLoadingTemplate ? (
            <div className="flex h-full min-h-[320px] items-center justify-center">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <textarea
              ref={textareaRef}
              value={draft}
              onChange={(e) => {
                setDraft(e.target.value)
              }}
              className="h-full min-h-[320px] w-full resize-none rounded-lg border border-border bg-muted/30 px-4 py-3 font-mono text-sm leading-relaxed text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              placeholder="输入系统提示词..."
            />
          )}
        </div>

        {/* 固定底部 */}
        <DialogFooter className="flex-none border-t px-6 py-3">
          <div className="mr-auto flex items-center gap-3">
            <Button
              variant="ghost"
              size="sm"
              onClick={handleReset}
              disabled={!isModified}
              className="gap-1.5 text-muted-foreground"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              恢复默认
            </Button>
            <span className="text-xs tabular-nums text-muted-foreground/50">
              {charCount.toLocaleString()} 字符
            </span>
          </div>
          <Button
            variant="outline"
            onClick={() => {
              onOpenChange(false)
            }}
          >
            取消
          </Button>
          <Button onClick={handleSave}>保存</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
