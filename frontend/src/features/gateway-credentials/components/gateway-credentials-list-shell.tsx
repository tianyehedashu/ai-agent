import { memo } from 'react'
import type React from 'react'

import { GatewayCredentialsPanelFallback } from '@/features/gateway-credentials/components/gateway-credentials-panel-fallback'
import { cn } from '@/lib/utils'

export interface GatewayCredentialsListShellProps {
  toolbar?: React.ReactNode
  hintSlot?: React.ReactNode
  isLoading?: boolean
  loadingMessage?: string
  isEmpty?: boolean
  emptySlot?: React.ReactNode
  children?: React.ReactNode
  paginationSlot?: React.ReactNode
  dialogsSlot?: React.ReactNode
  className?: string
}

export const GatewayCredentialsListShell = memo(function GatewayCredentialsListShell({
  toolbar,
  hintSlot,
  isLoading = false,
  loadingMessage,
  isEmpty = false,
  emptySlot,
  children,
  paginationSlot,
  dialogsSlot,
  className,
}: GatewayCredentialsListShellProps): React.JSX.Element {
  return (
    <div className={cn('flex min-h-0 flex-col rounded-lg border bg-card', className)}>
      {toolbar ? <div className="border-b p-3">{toolbar}</div> : null}
      {hintSlot ? (
        <div className="border-b px-3 py-2 text-xs text-muted-foreground">{hintSlot}</div>
      ) : null}

      <div className="min-h-[200px]">
        {isLoading ? (
          <GatewayCredentialsPanelFallback message={loadingMessage} />
        ) : isEmpty && emptySlot ? (
          <div className="p-4">{emptySlot}</div>
        ) : isEmpty ? (
          <p className="px-3 py-12 text-center text-sm text-muted-foreground">暂无凭据</p>
        ) : (
          children
        )}
      </div>

      {paginationSlot ? <div className="border-t px-3 py-2">{paginationSlot}</div> : null}
      {dialogsSlot}
    </div>
  )
})
