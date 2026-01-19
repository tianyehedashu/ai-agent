import { type KeyboardEvent, useRef, useEffect } from 'react'

import { Send, Paperclip, Globe, Loader2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'

interface ChatInputProps {
  value: string
  onChange: (value: string) => void
  onSend: () => void
  isLoading: boolean
}

export default function ChatInput({
  value,
  onChange,
  onSend,
  isLoading,
}: Readonly<ChatInputProps>): React.JSX.Element {
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`
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
          'relative flex flex-col rounded-2xl border border-border/60 bg-card/80 shadow-lg backdrop-blur-sm transition-all duration-200',
          'focus-within:border-primary/40 focus-within:shadow-xl focus-within:shadow-primary/5'
        )}
      >
        {/* Text Input */}
        <Textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="给 AI Agent 发送消息..."
          className="max-h-[200px] min-h-[52px] w-full resize-none border-0 bg-transparent px-4 py-3.5 text-[15px] leading-relaxed focus-visible:ring-0 focus-visible:ring-offset-0 placeholder:text-muted-foreground/40"
          rows={1}
          disabled={isLoading}
        />

        {/* Toolbar */}
        <div className="flex items-center justify-between border-t border-border/30 px-2 py-1.5">
          <div className="flex items-center">
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 rounded-lg text-muted-foreground/70 hover:bg-secondary hover:text-foreground"
              title="上传文件"
            >
              <Paperclip className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 rounded-lg text-muted-foreground/70 hover:bg-secondary hover:text-foreground"
              title="联网搜索"
            >
              <Globe className="h-4 w-4" />
            </Button>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-[11px] text-muted-foreground/40">
              {value.length > 0 && `${value.length} 字`}
            </span>
            <Button
              size="icon"
              onClick={onSend}
              disabled={!value.trim() || isLoading}
              title="发送 (Enter)"
              className={cn(
                'h-8 w-8 rounded-lg transition-all duration-200',
                value.trim() && !isLoading
                  ? 'bg-primary text-primary-foreground shadow-sm hover:bg-primary/90 hover:shadow-md'
                  : 'bg-secondary text-muted-foreground'
              )}
            >
              {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
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
