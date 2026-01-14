import { type KeyboardEvent, useRef } from 'react'

import { Send, Paperclip, Mic } from 'lucide-react'

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

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>): void => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      onSend()
    }
  }

  return (
    <div className="border-t bg-background p-4">
      <div className="mx-auto max-w-3xl">
        <div className="relative flex items-end gap-2 rounded-lg border bg-card p-2">
          {/* Attachment Button */}
          <Button variant="ghost" size="icon" className="flex-shrink-0">
            <Paperclip className="h-5 w-5 text-muted-foreground" />
          </Button>

          {/* Text Input */}
          <Textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => {
              onChange(e.target.value)
            }}
            onKeyDown={handleKeyDown}
            placeholder="输入消息..."
            className="max-h-[200px] min-h-[40px] flex-1 resize-none border-0 bg-transparent focus-visible:ring-0 focus-visible:ring-offset-0"
            rows={1}
            disabled={isLoading}
          />

          {/* Voice Button */}
          <Button variant="ghost" size="icon" className="flex-shrink-0">
            <Mic className="h-5 w-5 text-muted-foreground" />
          </Button>

          {/* Send Button */}
          <Button
            size="icon"
            onClick={onSend}
            disabled={!value.trim() || isLoading}
            className={cn('flex-shrink-0', value.trim() && !isLoading && 'animate-pulse-glow')}
          >
            <Send className="h-5 w-5" />
          </Button>
        </div>

        <p className="mt-2 text-center text-xs text-muted-foreground">
          AI Agent 可能会产生错误信息，请核实重要信息。
        </p>
      </div>
    </div>
  )
}
