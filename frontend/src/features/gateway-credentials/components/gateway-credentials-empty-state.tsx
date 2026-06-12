import type React from 'react'
import type { ComponentType } from 'react'

import { Key } from '@/lib/lucide-icons'

export interface GatewayCredentialsEmptyStateProps {
  icon?: ComponentType<{ className?: string }>
  title: string
  description?: React.ReactNode
  action?: React.ReactNode
}

export function GatewayCredentialsEmptyState({
  icon: Icon = Key,
  title,
  description,
  action,
}: GatewayCredentialsEmptyStateProps): React.JSX.Element {
  return (
    <div className="rounded-lg border border-dashed bg-muted/10 px-6 py-10 text-center">
      <Icon className="mx-auto h-8 w-8 text-muted-foreground/60" aria-hidden />
      <h3 className="mt-3 text-base font-semibold">{title}</h3>
      {description ? <p className="mt-1 text-sm text-muted-foreground">{description}</p> : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  )
}
