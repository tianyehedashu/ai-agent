import type React from 'react'
import { type KeyboardEvent, useRef, useEffect } from 'react'

import { Send, Loader2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'

interface ChatInputProps {
  value: string
  onChange: (value: string) => void
  onSend: () => void
  isLoading: boolean
  /** 工具栏左侧额外按钮（如「对话工具」） */
  toolbarLeftExtra?: React.ReactNode
  /** 输入框占位符 */
  placeholder?: string
}

export default function ChatInput({
  value,
  onChange,
  onSend,
  isLoading,
  toolbarLeftExtra,
  placeholder = '给 AI Agent 发送消息…',
}: Readonly<ChatInputProps>): React.JSX.Element {
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = `${String(Math.min(textareaRef.current.scrollHeight, 200))}px`
    }
  }, [value])

  // Focus on mount
  useEffect(() => {
    textareaRef.current?.focus()
  }, [])

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>): void => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (value.trim() && !isLoading) {
        onSend()
      }
    }
  }

  return (
    <>
      <div
        className={cn(
          'relative flex flex-col rounded-2xl border border-border bg-muted/30 shadow-sm transition-all duration-200',
          'border-border/70 bg-card/80 shadow-lg shadow-black/[0.04] backdrop-blur-xl focus-within:border-primary/50 focus-within:shadow-primary/10 focus-within:ring-2 focus-within:ring-primary/10 dark:shadow-black/30'
        )}
      >
        {/* Text Input */}
        <Textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => {
            onChange(e.target.value)
          }}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          className="max-h-[200px] min-h-[52px] w-full resize-none border-0 bg-transparent px-4 py-3.5 text-[15px] leading-relaxed placeholder:text-muted-foreground focus-visible:ring-0 focus-visible:ring-offset-0"
          rows={1}
          disabled={isLoading}
        />

        {/* Toolbar */}
        <div className="flex items-center justify-between border-t border-border/50 bg-muted/20 px-2 py-1.5">
          <div className="flex items-center gap-0.5">{toolbarLeftExtra}</div>

          <div className="flex items-center gap-2">
            <span className="text-[11px] text-muted-foreground/40">
              {value.length > 0 && `${String(value.length)} 字`}
            </span>
            <Button
              size="icon"
              onClick={onSend}
              disabled={!value.trim() || isLoading}
              aria-label="发送消息"
              title="发送"
              className={cn(
                'h-8 w-8 rounded-lg transition-colors',
                value.trim() && !isLoading
                  ? 'bg-primary text-primary-foreground shadow-sm shadow-primary/20 hover:bg-primary/90'
                  : 'bg-muted text-muted-foreground/50 shadow-none'
              )}
            >
              {isLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
            </Button>
          </div>
        </div>
      </div>

      {/* Disclaimer */}
      <p className="mt-2 text-center text-[11px] text-muted-foreground/40">
        AI 可能会产生错误信息，请核实重要内容
      </p>
    </>
  )
}
