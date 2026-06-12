import type React from 'react'

import { Loader2 } from '@/lib/lucide-icons'

export interface GatewayCredentialsPanelFallbackProps {
  message?: string
}

export function GatewayCredentialsPanelFallback({
  message = '加载中…',
}: GatewayCredentialsPanelFallbackProps): React.JSX.Element {
  return (
    <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground">
      <Loader2 className="h-4 w-4 animate-spin" />
      {message}
    </div>
  )
}
