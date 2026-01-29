import { useState } from 'react'

import {
  AlertTriangle,
  Brain,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  XCircle,
  FileText,
  Loader2,
  Clock,
  TerminalSquare,
} from 'lucide-react'

import { Card } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import type { ProcessEvent, ProcessEventKind } from '@/types'

interface ProcessPanelProps {
  events: ProcessEvent[]
  /** 默认是否展开，默认 false（折叠） */
  defaultExpanded?: boolean
}

type IconType = (props: { className?: string }) => React.JSX.Element

const kindMeta = {
  thinking: { label: '思考', icon: Brain as IconType, color: 'text-purple-500' },
  text: { label: '回复', icon: FileText as IconType, color: 'text-slate-500' },
  tool_call: { label: '工具', icon: TerminalSquare as IconType, color: 'text-blue-500' },
  tool_result: { label: '结果', icon: CheckCircle2 as IconType, color: 'text-emerald-500' },
  done: { label: '完成', icon: CheckCircle2 as IconType, color: 'text-green-500' },
  error: { label: '错误', icon: AlertTriangle as IconType, color: 'text-red-500' },
  interrupt: { label: '确认', icon: Clock as IconType, color: 'text-yellow-500' },
} satisfies Record<ProcessEventKind, { label: string; icon: IconType; color: string }>

/** 处理后的展示事件 */
interface DisplayEvent {
  id: string
  kind: ProcessEventKind
  title: string
  preview?: string
  details?: string
  isError?: boolean
  isSuccess?: boolean
  timestamp: string
  /** 聚合的事件数量（用于连续相同类型事件） */
  count?: number
}

/** 将原始事件转换为展示事件，智能聚合 */
function processEventsForDisplay(events: ProcessEvent[]): DisplayEvent[] {
  const result: DisplayEvent[] = []
  let textBuffer: ProcessEvent[] = []
  let thinkingBuffer: ProcessEvent[] = []

  const flushTextBuffer = (): void => {
    if (textBuffer.length === 0) return
    const combinedContent = textBuffer
      .map((e) => {
        const content = e.payload.content
        return typeof content === 'string' ? content : ''
      })
      .join('')

    if (combinedContent.trim()) {
      result.push({
        id: textBuffer[0].id,
        kind: 'text',
        title: '生成回复',
        preview: truncateText(combinedContent, 100),
        details: combinedContent.length > 100 ? combinedContent : undefined,
        timestamp: textBuffer[0].timestamp,
      })
    }
    textBuffer = []
  }

  const flushThinkingBuffer = (): void => {
    if (thinkingBuffer.length === 0) return
    // 合并连续的 thinking 事件
    const lastThinking = thinkingBuffer[thinkingBuffer.length - 1]
    const lastContent = lastThinking.payload.content
    const contentStr = typeof lastContent === 'string' ? lastContent : null

    result.push({
      id: thinkingBuffer[0].id,
      kind: 'thinking',
      title: thinkingBuffer.length > 1 ? `思考 ${String(thinkingBuffer.length)} 轮` : '思考中',
      preview: contentStr ? truncateText(contentStr, 100) : undefined,
      details: contentStr && contentStr.length > 100 ? contentStr : undefined,
      timestamp: thinkingBuffer[0].timestamp,
      count: thinkingBuffer.length,
    })
    thinkingBuffer = []
  }

  for (const event of events) {
    if (event.kind === 'text') {
      flushThinkingBuffer()
      textBuffer.push(event)
      continue
    }

    if (event.kind === 'thinking') {
      flushTextBuffer()
      thinkingBuffer.push(event)
      continue
    }

    // 遇到其他事件，先 flush buffers
    flushTextBuffer()
    flushThinkingBuffer()

    const displayEvent = convertToDisplayEvent(event)
    if (displayEvent) {
      result.push(displayEvent)
    }
  }

  // 处理末尾的 buffers
  flushTextBuffer()
  flushThinkingBuffer()

  return result
}

function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text
  return text.slice(0, maxLength) + '...'
}

function convertToDisplayEvent(event: ProcessEvent): DisplayEvent | null {
  const payload = event.payload

  switch (event.kind) {
    case 'tool_call': {
      const toolName = payload.tool_name ?? payload.name
      const args = payload.arguments ?? payload.args
      const toolNameStr = typeof toolName === 'string' ? toolName : '未知工具'
      let argsPreview = ''
      if (args && typeof args === 'object') {
        try {
          const argsStr = JSON.stringify(args, null, 2)
          argsPreview = truncateText(argsStr, 60)
        } catch {
          argsPreview = '[参数]'
        }
      }
      return {
        id: event.id,
        kind: 'tool_call',
        title: toolNameStr,
        preview: argsPreview || undefined,
        details: args ? JSON.stringify(args, null, 2) : undefined,
        timestamp: event.timestamp,
      }
    }

    case 'tool_result': {
      const success = payload.success === true
      const output = payload.output
      const error = payload.error
      const toolCallId = payload.tool_call_id ?? payload.toolCallId
      const durationMs = payload.duration_ms

      if (success) {
        const outputStr = typeof output === 'string' ? output : ''
        const durationStr = typeof durationMs === 'number' ? ` (${String(durationMs)}ms)` : ''
        return {
          id: event.id,
          kind: 'tool_result',
          title: `成功${durationStr}`,
          preview: outputStr ? truncateText(outputStr, 80) : '完成',
          details: outputStr && outputStr.length > 80 ? outputStr : undefined,
          isSuccess: true,
          timestamp: event.timestamp,
        }
      } else {
        const errorStr =
          typeof error === 'string' && error
            ? error
            : typeof output === 'string' && output
              ? output
              : '执行失败'
        const toolIdStr = typeof toolCallId === 'string' ? toolCallId : ''
        return {
          id: event.id,
          kind: 'tool_result',
          title: '失败',
          preview: truncateText(errorStr, 80),
          details: toolIdStr ? `ID: ${toolIdStr}\n\n${errorStr}` : errorStr,
          isError: true,
          timestamp: event.timestamp,
        }
      }
    }

    case 'error': {
      const errorMsg = payload.error
      const errorStr = typeof errorMsg === 'string' ? errorMsg : '发生错误'
      return {
        id: event.id,
        kind: 'error',
        title: '错误',
        preview: errorStr,
        isError: true,
        timestamp: event.timestamp,
      }
    }

    case 'interrupt': {
      const reason = payload.reason
      const pendingAction = payload.pendingAction as { name?: string } | undefined
      const reasonStr = typeof reason === 'string' ? reason : '需要确认'
      const actionName = pendingAction?.name
      const actionStr = typeof actionName === 'string' ? actionName : ''
      return {
        id: event.id,
        kind: 'interrupt',
        title: actionStr ? `确认: ${actionStr}` : '等待确认',
        preview: reasonStr,
        timestamp: event.timestamp,
      }
    }

    case 'done': {
      const iterations = payload.iterations ?? payload.iteration
      const toolIterations = payload.tool_iterations
      const totalTokens = payload.total_tokens ?? payload.totalTokens
      const stats: string[] = []
      if (typeof iterations === 'number' && iterations > 0) stats.push(`${String(iterations)} 轮`)
      if (typeof toolIterations === 'number' && toolIterations > 0)
        stats.push(`${String(toolIterations)} 次调用`)
      if (typeof totalTokens === 'number' && totalTokens > 0)
        stats.push(`${String(totalTokens)} tokens`)
      return {
        id: event.id,
        kind: 'done',
        title: '完成',
        preview: stats.length > 0 ? stats.join(' · ') : undefined,
        timestamp: event.timestamp,
      }
    }

    default:
      return null
  }
}

interface ProcessEventItemProps {
  event: DisplayEvent
  isCompleted: boolean
  compact?: boolean
}

/** 紧凑的事件项 */
function ProcessEventItem({
  event,
  isCompleted,
  compact = false,
}: Readonly<ProcessEventItemProps>): React.JSX.Element {
  const [isExpanded, setIsExpanded] = useState(false)
  const meta = kindMeta[event.kind]
  const Icon = meta.icon
  const hasDetails = Boolean(event.details)

  const getIcon = (): React.JSX.Element => {
    if (event.isError) {
      return <XCircle className="h-3.5 w-3.5 text-red-500" />
    }
    if (event.kind === 'thinking' && !isCompleted) {
      return <Loader2 className={cn('h-3.5 w-3.5 animate-spin', meta.color)} />
    }
    return <Icon className={cn('h-3.5 w-3.5', meta.color)} />
  }

  if (compact) {
    // 紧凑模式：单行显示
    return (
      <div
        className={cn(
          'flex items-center gap-2 rounded px-2 py-1 text-xs',
          event.isError && 'bg-red-500/10',
          event.isSuccess && 'bg-emerald-500/5'
        )}
      >
        {getIcon()}
        <span className={cn('font-medium', event.isError && 'text-red-600')}>{event.title}</span>
        {event.preview && (
          <span className="truncate text-muted-foreground">{truncateText(event.preview, 40)}</span>
        )}
      </div>
    )
  }

  // 标准模式
  return (
    <div
      className={cn(
        'flex items-start gap-2 rounded-md border px-2.5 py-1.5',
        event.isError
          ? 'border-red-500/30 bg-red-500/5'
          : event.isSuccess
            ? 'border-emerald-500/20 bg-emerald-500/5'
            : 'border-border/40 bg-muted/10'
      )}
    >
      <div className="mt-0.5 shrink-0">{getIcon()}</div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          {hasDetails && (
            <button
              type="button"
              onClick={() => { setIsExpanded(!isExpanded); }}
              className="shrink-0 rounded p-0.5 hover:bg-muted/50"
            >
              {isExpanded ? (
                <ChevronDown className="h-3 w-3 text-muted-foreground" />
              ) : (
                <ChevronRight className="h-3 w-3 text-muted-foreground" />
              )}
            </button>
          )}
          <span
            className={cn(
              'text-xs font-medium',
              event.isError ? 'text-red-600 dark:text-red-400' : 'text-foreground'
            )}
          >
            {event.title}
          </span>
          {event.count && event.count > 1 && (
            <span className="rounded bg-muted/60 px-1 py-0.5 text-[10px] text-muted-foreground">
              ×{event.count}
            </span>
          )}
        </div>
        {event.preview && !isExpanded && (
          <div className="mt-0.5 truncate text-[11px] text-muted-foreground">{event.preview}</div>
        )}
        {isExpanded && event.details && (
          <pre className="mt-1.5 max-h-40 overflow-auto rounded bg-muted/30 p-2 text-[10px] text-muted-foreground">
            {event.details}
          </pre>
        )}
      </div>
    </div>
  )
}

export function ProcessPanel({
  events,
  defaultExpanded = false,
}: Readonly<ProcessPanelProps>): React.JSX.Element {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded)
  const [isFullHeight, setIsFullHeight] = useState(false) // 是否展开全部（无高度限制）
  const displayEvents = processEventsForDisplay(events)
  const isCompleted = events.some((e) => e.kind === 'done' || e.kind === 'error')

  // 统计
  const thinkingCount = events.filter((e) => e.kind === 'thinking').length
  const toolCount = events.filter((e) => e.kind === 'tool_call').length
  const errorCount = displayEvents.filter((e) => e.isError).length

  // 是否需要显示"展开全部"按钮（事件较多时）
  const needsExpandAll = displayEvents.length > 5

  // 生成摘要徽章
  const badges = [
    thinkingCount > 0 && { label: `思考 ${String(thinkingCount)}`, color: 'text-purple-500' },
    toolCount > 0 && { label: `工具 ${String(toolCount)}`, color: 'text-blue-500' },
    errorCount > 0 && { label: `失败 ${String(errorCount)}`, color: 'text-red-500' },
  ].filter(Boolean) as Array<{ label: string; color: string }>

  return (
    <Card className="mt-2 overflow-hidden border-muted/40 bg-muted/10">
      {/* 可点击的头部 */}
      <button
        type="button"
        onClick={() => { setIsExpanded(!isExpanded); }}
        className="flex w-full items-center gap-2 px-3 py-2 text-left transition-colors hover:bg-muted/20"
      >
        {/* 展开/折叠图标 */}
        {isExpanded ? (
          <ChevronDown className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        )}

        {/* 状态图标 */}
        {isCompleted ? (
          <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-green-500" />
        ) : (
          <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-primary" />
        )}

        {/* 标题 */}
        <span className="text-xs font-medium text-foreground">
          {isCompleted ? '执行完成' : '执行中...'}
        </span>

        {/* 徽章 */}
        <div className="flex items-center gap-1.5">
          {badges.map((badge) => (
            <span key={badge.label} className={cn('text-[10px]', badge.color)}>
              {badge.label}
            </span>
          ))}
        </div>

        {/* 步骤数 */}
        <span className="ml-auto text-[10px] text-muted-foreground">
          {displayEvents.length} 步
        </span>
      </button>

      {/* 展开的事件列表 */}
      {isExpanded && (
        <div
          className={cn(
            'space-y-1.5 overflow-y-auto border-t border-border/30 p-2',
            !isFullHeight && 'max-h-64'
          )}
        >
          {displayEvents.map((event) => (
            <ProcessEventItem
              key={event.id}
              event={event}
              isCompleted={isCompleted}
              compact={displayEvents.length > 10 && !isFullHeight}
            />
          ))}
        </div>
      )}

      {/* 展开全部 / 收起 按钮 */}
      {isExpanded && needsExpandAll && (
        <button
          type="button"
          onClick={() => { setIsFullHeight(!isFullHeight); }}
          className="flex w-full items-center justify-center gap-1 border-t border-border/30 py-1.5 text-[10px] text-muted-foreground transition-colors hover:bg-muted/20 hover:text-foreground"
        >
          {isFullHeight ? (
            <>
              <ChevronDown className="h-3 w-3 rotate-180" />
              收起
            </>
          ) : (
            <>
              <ChevronDown className="h-3 w-3" />
              展开全部
            </>
          )}
        </button>
      )}
    </Card>
  )
}
