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

import { AlertCircle, CheckCircle2, HelpCircle, Hourglass, Lock } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { cn, formatDate, formatRelativeTime } from '@/lib/utils'
import type { ModelTestStatus } from '@/types/user-model'

/**
 * Entitlement 状态：与后端 ``EntitlementGuard.status_for_models`` 一致：
 * - active        - 命中且未耗尽
 * - exhausted     - 命中但配额已耗尽（HTTP 429 不 fallback）
 * - resetting     - 命中已耗尽，但在窗口边界附近（即将自动恢复）
 * - expired       - plan 过期但尚未续期
 * - none          - 未配置 plan，默认放行
 */
export type EntitlementStatus = 'active' | 'exhausted' | 'resetting' | 'expired' | 'none'

export interface ModelStatusBadgeProps {
  status: ModelTestStatus
  testedAt: string | null
  /** 失败时后端落库的 last_test_reason，用于 tooltip 排查 */
  reason?: string | null
  /** 窄列表行：仅图标+短标签，相对时间见 tooltip */
  compact?: boolean
  className?: string
  /** 当前调用方 entitlement plan 命中情况；优先级低于 `status` 失败 */
  entitlementStatus?: EntitlementStatus
  /** entitlement 自动恢复时刻（ISO），用于 resetting/exhausted 的 tooltip */
  entitlementResetAt?: string | null
}

interface StatusVisual {
  label: string
  Icon: typeof CheckCircle2
  /** Tailwind classes pinned to status semantic color (避开 Badge 默认 primary/destructive 撞色) */
  className: string
}

type StatusKey =
  | 'success'
  | 'failed'
  | 'unknown'
  | 'entitlement_exhausted'
  | 'entitlement_resetting'
  | 'entitlement_expired'

const VISUAL_BY_STATUS: Record<StatusKey, StatusVisual> = {
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
  entitlement_exhausted: {
    label: '套餐耗尽',
    Icon: Lock,
    className:
      'border-transparent bg-amber-100 text-amber-700 hover:bg-amber-100 dark:bg-amber-900/40 dark:text-amber-300',
  },
  entitlement_resetting: {
    label: '即将恢复',
    Icon: Hourglass,
    className:
      'border-transparent bg-sky-100 text-sky-700 hover:bg-sky-100 dark:bg-sky-900/40 dark:text-sky-300',
  },
  entitlement_expired: {
    label: '套餐过期',
    Icon: Lock,
    className:
      'border-transparent bg-zinc-100 text-zinc-700 hover:bg-zinc-100 dark:bg-zinc-900/40 dark:text-zinc-300',
  },
}

export function ModelStatusBadge({
  status,
  testedAt,
  reason,
  compact = false,
  className,
  entitlementStatus,
  entitlementResetAt,
}: ModelStatusBadgeProps): React.JSX.Element {
  const baseKey: 'success' | 'failed' | 'unknown' =
    status === 'success' ? 'success' : status === 'failed' ? 'failed' : 'unknown'
  // 仅当连通性测试本身没有失败时才用 entitlement 覆盖标签
  const key: StatusKey =
    baseKey === 'failed'
      ? 'failed'
      : entitlementStatus === 'exhausted'
        ? 'entitlement_exhausted'
        : entitlementStatus === 'resetting'
          ? 'entitlement_resetting'
          : entitlementStatus === 'expired'
            ? 'entitlement_expired'
            : baseKey
  const visual = VISUAL_BY_STATUS[key]
  const Icon = visual.Icon

  const relative = testedAt ? formatRelativeTime(testedAt) : null
  const absolute = testedAt ? formatDate(testedAt) : null
  const resetAbs = entitlementResetAt ? formatDate(entitlementResetAt) : null
  const trimmedReason = reason?.trim()
  const tooltipText =
    key === 'entitlement_exhausted'
      ? `当前调用方套餐配额已耗尽${resetAbs ? `\n预计恢复: ${resetAbs}` : ''}`
      : key === 'entitlement_resetting'
        ? `配额即将自动恢复${resetAbs ? `\n时间: ${resetAbs}` : ''}`
        : key === 'entitlement_expired'
          ? '套餐已过期，请联系管理员续期或更换 vkey'
          : key === 'unknown'
            ? '尚未发起连通性测试'
            : key === 'failed' && trimmedReason
              ? `上次测试: ${absolute ?? '—'}\n原因: ${trimmedReason}`
              : `上次测试: ${absolute ?? '—'}${key === 'failed' ? '（失败，可点测试按钮重试）' : ''}`

  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>
          <Badge
            className={cn(
              'shrink-0 whitespace-nowrap font-medium',
              compact ? 'gap-0.5 px-1.5 py-0.5 text-[11px]' : 'gap-1 px-2 py-0.5',
              visual.className,
              className
            )}
          >
            <Icon
              className={cn('shrink-0', compact ? 'h-2.5 w-2.5' : 'h-3 w-3')}
              aria-hidden="true"
            />
            <span>{visual.label}</span>
            {!compact && relative ? (
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
