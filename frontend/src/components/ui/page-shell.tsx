import type { ComponentType, HTMLAttributes, ReactNode } from 'react'

import { cn } from '@/lib/utils'

type PageShellSize = 'default' | 'wide' | 'full'

const shellSizeClass: Record<PageShellSize, string> = {
  default: 'max-w-5xl',
  wide: 'max-w-7xl',
  full: 'max-w-none',
}

export interface PageShellProps extends HTMLAttributes<HTMLDivElement> {
  size?: PageShellSize
}

export function PageShell({
  size = 'wide',
  className,
  ...props
}: Readonly<PageShellProps>): React.JSX.Element {
  return (
    <div
      className={cn('mx-auto w-full px-4 py-5 sm:px-6 lg:px-8', shellSizeClass[size], className)}
      {...props}
    />
  )
}

export interface PageHeaderProps extends HTMLAttributes<HTMLElement> {
  title: string
  description?: ReactNode
  eyebrow?: string
  icon?: ComponentType<{ className?: string }>
  actions?: ReactNode
}

export function PageHeader({
  title,
  description,
  eyebrow,
  icon: Icon,
  actions,
  className,
  ...props
}: Readonly<PageHeaderProps>): React.JSX.Element {
  return (
    <section
      className={cn(
        'elevated-panel overflow-hidden rounded-xl px-5 py-4 sm:px-6',
        'bg-[linear-gradient(135deg,hsl(var(--card)/0.96),hsl(var(--surface-raised)/0.78))]',
        className
      )}
      {...props}
    >
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex min-w-0 items-start gap-4">
          {Icon ? (
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg border border-primary/20 bg-primary/10 text-primary shadow-sm shadow-primary/10">
              <Icon className="h-5 w-5" />
            </div>
          ) : null}
          <div className="min-w-0">
            {eyebrow ? (
              <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-primary/80">
                {eyebrow}
              </p>
            ) : null}
            <h1 className="truncate text-2xl font-semibold tracking-tight text-foreground">
              {title}
            </h1>
            {description ? (
              <p className="mt-1 max-w-3xl text-sm leading-6 text-muted-foreground">
                {description}
              </p>
            ) : null}
          </div>
        </div>
        {actions ? (
          <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>
        ) : null}
      </div>
    </section>
  )
}
