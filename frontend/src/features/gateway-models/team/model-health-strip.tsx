import { Loader2 } from 'lucide-react'

import type { GatewayModel } from '@/api/gateway'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

import { summarizeHealth } from '../utils'

import type { HealthFilter } from '../constants'

interface ModelHealthStripProps {
  models: GatewayModel[]
  healthFilter: HealthFilter
  onHealthFilterChange: (f: HealthFilter) => void
  canWrite: boolean
  onTestAll?: () => void
  testingAll?: boolean
}

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
  variant?: 'success' | 'failed' | 'muted'
}): React.JSX.Element {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'rounded-full border px-2.5 py-0.5 text-xs transition-colors',
        active && 'border-primary bg-primary/10 text-primary',
        !active && 'border-border text-muted-foreground hover:bg-muted/50',
        variant === 'success' && !active && count > 0 && 'border-emerald-200/60',
        variant === 'failed' && !active && count > 0 && 'border-rose-200/60'
      )}
    >
      {label} <span className="tabular-nums">{count}</span>
    </button>
  )
}

export function ModelHealthStrip({
  models,
  healthFilter,
  onHealthFilterChange,
  canWrite,
  onTestAll,
  testingAll,
}: ModelHealthStripProps): React.JSX.Element {
  const { total, success, failed, unknown } = summarizeHealth(models)

  if (total === 0) return <></>

  return (
    <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border bg-muted/20 px-3 py-2">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-medium text-muted-foreground">健康</span>
        <FilterChip
          active={healthFilter === 'all'}
          label="全部"
          count={total}
          onClick={() => {
            onHealthFilterChange('all')
          }}
        />
        <FilterChip
          active={healthFilter === 'success'}
          label="可用"
          count={success}
          variant="success"
          onClick={() => {
            onHealthFilterChange('success')
          }}
        />
        <FilterChip
          active={healthFilter === 'failed'}
          label="不可用"
          count={failed}
          variant="failed"
          onClick={() => {
            onHealthFilterChange('failed')
          }}
        />
        <FilterChip
          active={healthFilter === 'unknown'}
          label="未测试"
          count={unknown}
          onClick={() => {
            onHealthFilterChange('unknown')
          }}
        />
      </div>
      {canWrite && onTestAll ? (
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="h-7 text-xs"
          disabled={testingAll}
          onClick={onTestAll}
        >
          {testingAll ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : null}
          测试全部可测模型
        </Button>
      ) : null}
    </div>
  )
}
