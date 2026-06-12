import type React from 'react'
import type { ComponentType } from 'react'

export interface CredentialTableGroupRowProps {
  icon: ComponentType<{ className?: string }>
  title: React.ReactNode
  badges?: React.ReactNode
  actions?: React.ReactNode
  colSpan?: number
}

export function CredentialTableGroupRow({
  icon: Icon,
  title,
  badges,
  actions,
  colSpan = 5,
}: CredentialTableGroupRowProps): React.JSX.Element {
  return (
    <tr className="border-b bg-muted/30">
      <td
        colSpan={colSpan}
        className="sticky top-0 z-10 px-4 py-2.5 backdrop-blur-sm supports-[backdrop-filter]:bg-muted/20"
      >
        <div className="flex flex-wrap items-center gap-2">
          <Icon className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="truncate font-medium">{title}</span>
              {badges}
            </div>
          </div>
          {actions ? <div className="flex flex-wrap items-center gap-1">{actions}</div> : null}
        </div>
      </td>
    </tr>
  )
}
