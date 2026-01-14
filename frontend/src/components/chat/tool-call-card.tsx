/**
 * Tool Call Card - 工具调用卡片
 *
 * 显示工具调用的详情
 */

import { useState } from 'react'

import { ChevronDown, ChevronRight, Terminal, Code, FileText, Search } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import type { ToolCall } from '@/types'

interface ToolCallCardProps {
  toolCall: ToolCall
  result?: {
    success: boolean
    output: string
    error?: string
  }
  isPending?: boolean
}

const toolIcons: Record<string, React.ComponentType<{ className?: string }>> = {
  run_shell: Terminal,
  run_python: Code,
  read_file: FileText,
  write_file: FileText,
  search_code: Search,
  web_search: Search,
  grep: Search,
}

export function ToolCallCard({
  toolCall,
  result,
  isPending,
}: Readonly<ToolCallCardProps>): React.JSX.Element {
  const [isExpanded, setIsExpanded] = useState(false)

  const Icon = toolIcons[toolCall.name] ?? Terminal

  return (
    <Card
      className={cn(
        'p-3 transition-colors',
        isPending && 'border-yellow-500/50 bg-yellow-500/5',
        result?.success === false && 'border-red-500/50 bg-red-500/5',
        result?.success === true && 'border-green-500/50 bg-green-500/5'
      )}
    >
      <button
        type="button"
        className="flex w-full cursor-pointer items-center gap-2 text-left"
        onClick={() => {
          setIsExpanded(!isExpanded)
        }}
      >
        <Button variant="ghost" size="icon" className="h-5 w-5 p-0">
          {isExpanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        </Button>

        <Icon className="h-4 w-4 text-muted-foreground" />

        <span className="font-mono text-sm font-medium">{toolCall.name}</span>

        {isPending && (
          <span className="ml-auto animate-pulse text-xs text-yellow-500">执行中...</span>
        )}

        {result && (
          <span
            className={cn('ml-auto text-xs', result.success ? 'text-green-500' : 'text-red-500')}
          >
            {result.success ? '成功' : '失败'}
          </span>
        )}
      </button>

      {isExpanded && (
        <div className="mt-3 space-y-2">
          {/* 参数 */}
          <div>
            <p className="mb-1 text-xs text-muted-foreground">参数:</p>
            <pre className="overflow-x-auto rounded bg-muted/50 p-2 text-xs">
              {JSON.stringify(toolCall.arguments, null, 2)}
            </pre>
          </div>

          {/* 结果 */}
          {result && (
            <div>
              <p className="mb-1 text-xs text-muted-foreground">
                {result.success ? '输出:' : '错误:'}
              </p>
              <pre
                className={cn(
                  'max-h-40 overflow-x-auto rounded p-2 text-xs',
                  result.success ? 'bg-muted/50' : 'bg-red-500/10'
                )}
              >
                {result.success ? result.output : result.error}
              </pre>
            </div>
          )}
        </div>
      )}
    </Card>
  )
}
