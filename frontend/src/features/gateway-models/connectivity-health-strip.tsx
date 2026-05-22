import { memo, useMemo } from 'react'

import { Button } from '@/components/ui/button'
import { Loader2 } from '@/lib/lucide-icons'
import { cn } from '@/lib/utils'

import { summarizeHealth, type ModelWithConnectivityStatus } from './utils'

import type { HealthFilter } from './constants'

interface ConnectivityHealthStripProps {
  models: readonly ModelWithConnectivityStatus[]
  healthFilter: HealthFilter
  onHealthFilterChange: (f: HealthFilter) => void
  canWrite: boolean
  onTestAll?: () => void
  testingAll?: boolean
  /** 探活失败项一键删除（与当前 healthFilter 无关） */
  onDeleteFailed?: () => void
  deletingFailed?: boolean
}

const FILTER_OPTIONS: ReadonlyArray<{
  value: HealthFilter
  label: string
  variant?: 'success' | 'failed'
}> = [
  { value: 'all', label: '全部' },
  { value: 'success', label: '可用', variant: 'success' },
  { value: 'failed', label: '不可用', variant: 'failed' },
  { value: 'unknown', label: '未测试' },
]

function FilterChip({
  active,
  label,
  count,
  onClick,
  variant,
}: {
  active: boolean
  label: string
  count: number
  onClick: () => void
  variant?: 'success' | 'failed'
}): React.JSX.Element {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'rounded-md px-2 py-1 text-xs font-medium transition-colors',
        active && 'bg-background text-foreground shadow-sm',
        !active && 'text-muted-foreground hover:text-foreground',
        variant === 'success' && !active && count > 0 && 'text-emerald-600 dark:text-emerald-400',
        variant === 'failed' && !active && count > 0 && 'text-rose-600 dark:text-rose-400'
      )}
    >
      {label}
      <span className="ml-1 tabular-nums opacity-70">{count}</span>
    </button>
  )
}

/** 团队 / 个人模型清单共用的连通性健康筛选与「测试全部」入口 */
export const ConnectivityHealthStrip = memo(function ConnectivityHealthStrip({
  models,
  healthFilter,
  onHealthFilterChange,
  canWrite,
  onTestAll,
  testingAll,
  onDeleteFailed,
  deletingFailed = false,
}: ConnectivityHealthStripProps): React.JSX.Element {
  const counts = useMemo(() => summarizeHealth(models), [models])

  const countByFilter = useMemo(
    (): Record<HealthFilter, number> => ({
      all: counts.total,
      success: counts.success,
      failed: counts.failed,
      unknown: counts.unknown,
    }),
    [counts]
  )

  if (counts.total === 0) return <></>

  return (
    <div className="flex min-w-0 flex-1 flex-wrap items-center gap-1">
      <div className="flex flex-wrap items-center gap-0.5 rounded-md bg-muted/50 p-0.5">
        {FILTER_OPTIONS.map((opt) => (
          <FilterChip
            key={opt.value}
            active={healthFilter === opt.value}
            label={opt.label}
            count={countByFilter[opt.value]}
            variant={opt.variant}
            onClick={() => {
              onHealthFilterChange(opt.value)
            }}
          />
        ))}
      </div>
      <div className="ml-auto flex shrink-0 items-center gap-1">
        {canWrite && counts.failed > 0 && onDeleteFailed ? (
          <Button
            type="button"
            size="sm"
            variant="ghost"
            className="h-7 px-2 text-xs text-destructive hover:text-destructive"
            disabled={testingAll === true || deletingFailed}
            onClick={onDeleteFailed}
          >
            {deletingFailed ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : null}
            删除不可用 ({counts.failed})
          </Button>
        ) : null}
        {canWrite && onTestAll ? (
          <Button
            type="button"
            size="sm"
            variant="ghost"
            className="h-7 px-2 text-xs text-muted-foreground"
            disabled={testingAll === true || deletingFailed}
            onClick={onTestAll}
          >
            {testingAll ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : null}
            测试全部
          </Button>
        ) : null}
      </div>
    </div>
  )
})

/** @deprecated 使用 `ConnectivityHealthStrip` */
export const ModelHealthStrip = ConnectivityHealthStrip
