import type { ComponentType, HTMLAttributes, ReactNode } from 'react'

import { cn } from '@/lib/utils'

type MetricTone = 'default' | 'success' | 'warning' | 'info'

const toneClass: Record<MetricTone, string> = {
  default: 'border-primary/20 bg-primary/10 text-primary',
  success: 'border-success/20 bg-success/10 text-success',
  warning: 'border-warning/25 bg-warning/10 text-warning',
  info: 'border-info/20 bg-info/10 text-info',
}

const barToneClass: Record<MetricTone, string> = {
  default: 'bg-primary/55',
  success: 'bg-success/60',
  warning: 'bg-warning/65',
  info: 'bg-info/60',
}

const SPARK_BARS = [38, 64, 46, 78, 58, 86, 70]

export interface MetricCardProps extends HTMLAttributes<HTMLDivElement> {
  title: string
  value: ReactNode
  description?: ReactNode
  icon?: ComponentType<{ className?: string }>
  tone?: MetricTone
  loading?: boolean
}

export function MetricCard({
  title,
  value,
  description,
  icon: Icon,
  tone = 'default',
  loading = false,
  className,
  ...props
}: Readonly<MetricCardProps>): React.JSX.Element {
  return (
    <div
      className={cn(
        'group relative overflow-hidden rounded-lg border border-border/70 bg-card/90 p-4 shadow-sm shadow-black/[0.03] transition-colors hover:border-primary/30 dark:shadow-black/20',
        className
      )}
      {...props}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-medium text-muted-foreground">{title}</p>
          <div className="mt-2 text-2xl font-semibold tabular-nums tracking-tight text-foreground">
            {loading ? '—' : value}
          </div>
        </div>
        {Icon ? (
          <div
            className={cn(
              'flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border',
              toneClass[tone]
            )}
          >
            <Icon className="h-4 w-4" />
          </div>
        ) : null}
      </div>
      <div className="mt-4 flex items-end justify-between gap-3">
        <div className="flex h-7 items-end gap-1" aria-hidden="true">
          {SPARK_BARS.map((height, index) => (
            <span
              key={index}
              className={cn('w-1 rounded-full opacity-80', barToneClass[tone])}
              style={{ height: `${String(height)}%` }}
            />
          ))}
        </div>
        {description ? (
          <p className="max-w-[9rem] text-right text-[11px] leading-4 text-muted-foreground">
            {description}
          </p>
        ) : null}
      </div>
    </div>
  )
}
