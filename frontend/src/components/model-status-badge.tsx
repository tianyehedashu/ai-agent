/**
 * ModelStatusBadge - 模型连通性状态徽标
 *
 * 与后端 `last_test_status` / `last_tested_at` / `last_test_reason` 同语义：
 * - 'success' → 绿色「可用」+ 上次测试相对时间
 * - 'failed'  → 红色「不可用」+ 上次测试相对时间；tooltip 可展示 `reason`
 * - null      → 灰色「未测试」
 *
 * 用户模型与 Gateway 团队模型共用此组件，保持视觉一致。
 */

import { AlertCircle, CheckCircle2, HelpCircle } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { cn, formatDate, formatRelativeTime } from '@/lib/utils'
import type { ModelTestStatus } from '@/types/user-model'

export interface ModelStatusBadgeProps {
  status: ModelTestStatus
  testedAt: string | null
  /** 失败时后端落库的 last_test_reason，用于 tooltip 排查 */
  reason?: string | null
  className?: string
}

interface StatusVisual {
  label: string
  Icon: typeof CheckCircle2
  /** Tailwind classes pinned to status semantic color (避开 Badge 默认 primary/destructive 撞色) */
  className: string
}

const VISUAL_BY_STATUS: Record<'success' | 'failed' | 'unknown', StatusVisual> = {
  success: {
    label: '可用',
    Icon: CheckCircle2,
    className:
      'border-transparent bg-emerald-100 text-emerald-700 hover:bg-emerald-100 dark:bg-emerald-900/40 dark:text-emerald-300',
  },
  failed: {
    label: '不可用',
    Icon: AlertCircle,
    className:
      'border-transparent bg-rose-100 text-rose-700 hover:bg-rose-100 dark:bg-rose-900/40 dark:text-rose-300',
  },
  unknown: {
    label: '未测试',
    Icon: HelpCircle,
    className: 'border-transparent bg-muted text-muted-foreground hover:bg-muted',
  },
}

export function ModelStatusBadge({
  status,
  testedAt,
  reason,
  className,
}: ModelStatusBadgeProps): React.JSX.Element {
  const key: 'success' | 'failed' | 'unknown' =
    status === 'success' ? 'success' : status === 'failed' ? 'failed' : 'unknown'
  const visual = VISUAL_BY_STATUS[key]
  const Icon = visual.Icon

  const relative = testedAt ? formatRelativeTime(testedAt) : null
  const absolute = testedAt ? formatDate(testedAt) : null
  const trimmedReason = reason?.trim()
  const tooltipText =
    key === 'unknown'
      ? '尚未发起连通性测试'
      : key === 'failed' && trimmedReason
        ? `上次测试: ${absolute ?? '—'}\n原因: ${trimmedReason}`
        : `上次测试: ${absolute ?? '—'}${key === 'failed' ? '（失败，可点测试按钮重试）' : ''}`

  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>
          <Badge className={cn('gap-1 px-2 py-0.5 font-medium', visual.className, className)}>
            <Icon className="h-3 w-3" aria-hidden="true" />
            <span>{visual.label}</span>
            {relative ? (
              <span className="text-[10px] font-normal opacity-80">· {relative}</span>
            ) : null}
          </Badge>
        </TooltipTrigger>
        <TooltipContent className="max-w-sm whitespace-pre-wrap break-words">
          {tooltipText}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}
