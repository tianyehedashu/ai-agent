/**
 * Tool Call Card - 工具调用卡片
 *
 * 显示工具调用的详情
 */

import { useState } from 'react'
import { ChevronDown, ChevronRight, Terminal, Code, FileText, Search } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
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

export function ToolCallCard({ toolCall, result, isPending }: ToolCallCardProps) {
  const [isExpanded, setIsExpanded] = useState(false)

  const Icon = toolIcons[toolCall.name] || Terminal

  return (
    <Card
      className={cn(
        'p-3 transition-colors',
        isPending && 'border-yellow-500/50 bg-yellow-500/5',
        result?.success === false && 'border-red-500/50 bg-red-500/5',
        result?.success === true && 'border-green-500/50 bg-green-500/5'
      )}
    >
      <div
        className="flex items-center gap-2 cursor-pointer"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <Button variant="ghost" size="icon" className="h-5 w-5 p-0">
          {isExpanded ? (
            <ChevronDown className="h-3 w-3" />
          ) : (
            <ChevronRight className="h-3 w-3" />
          )}
        </Button>

        <Icon className="h-4 w-4 text-muted-foreground" />

        <span className="font-mono text-sm font-medium">{toolCall.name}</span>

        {isPending && (
          <span className="ml-auto text-xs text-yellow-500 animate-pulse">
            执行中...
          </span>
        )}

        {result && (
          <span
            className={cn(
              'ml-auto text-xs',
              result.success ? 'text-green-500' : 'text-red-500'
            )}
          >
            {result.success ? '成功' : '失败'}
          </span>
        )}
      </div>

      {isExpanded && (
        <div className="mt-3 space-y-2">
          {/* 参数 */}
          <div>
            <p className="text-xs text-muted-foreground mb-1">参数:</p>
            <pre className="text-xs bg-muted/50 p-2 rounded overflow-x-auto">
              {JSON.stringify(toolCall.arguments, null, 2)}
            </pre>
          </div>

          {/* 结果 */}
          {result && (
            <div>
              <p className="text-xs text-muted-foreground mb-1">
                {result.success ? '输出:' : '错误:'}
              </p>
              <pre
                className={cn(
                  'text-xs p-2 rounded overflow-x-auto max-h-40',
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
