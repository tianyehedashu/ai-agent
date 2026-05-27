/**
 * Gateway 列表/统计页统一的刷新按钮。
 */

import type React from 'react'

import { Button } from '@/components/ui/button'
import { RefreshCw } from '@/lib/lucide-icons'
import { cn } from '@/lib/utils'

export interface GatewayRefreshButtonProps {
  isFetching: boolean
  onRefresh: () => unknown
  ariaLabel?: string
  className?: string
}

export function GatewayRefreshButton({
  isFetching,
  onRefresh,
  ariaLabel = '刷新',
  className,
}: GatewayRefreshButtonProps): React.JSX.Element {
  return (
    <Button
      type="button"
      size="icon"
      variant="outline"
      className={cn('h-9 w-9', className)}
      title="刷新"
      aria-label={ariaLabel}
      disabled={isFetching}
      onClick={() => {
        void onRefresh()
      }}
    >
      <RefreshCw className={cn('h-4 w-4', isFetching && 'animate-spin')} />
    </Button>
  )
}
