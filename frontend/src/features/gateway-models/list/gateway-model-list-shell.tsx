import { memo } from 'react'

import { ScrollArea } from '@/components/ui/scroll-area'
import { Loader2 } from '@/lib/lucide-icons'
import { cn } from '@/lib/utils'

import type { GatewayModelListShellProps } from './types'

export const GatewayModelListShell = memo(function GatewayModelListShell({
  capabilities,
  bannerSlot,
  connectivityBanner,
  toolbar,
  batchBar,
  headerSlot,
  isLoading = false,
  isEmpty = false,
  emptySlot,
  children,
  paginationSlot,
  dialogsSlot,
  className,
}: GatewayModelListShellProps): React.JSX.Element {
  const showConnectivityBanner =
    capabilities.connectivityBanner !== false && connectivityBanner !== undefined
  const showHeader = capabilities.headerSlot === true && headerSlot !== undefined

  return (
    <div className={cn('flex min-h-0 flex-col rounded-lg border bg-card', className)}>
      {bannerSlot}
      {showConnectivityBanner ? connectivityBanner : null}
      {toolbar}
      {batchBar}
      {showHeader ? headerSlot : null}

      <ScrollArea className="min-h-[280px] flex-1">
        {isLoading ? (
          <div className="flex items-center justify-center gap-2 py-12 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            加载中…
          </div>
        ) : isEmpty && emptySlot ? (
          emptySlot
        ) : isEmpty ? (
          <p className="px-3 py-12 text-center text-sm text-muted-foreground">无匹配模型</p>
        ) : (
          <div className="pr-3">{children}</div>
        )}
      </ScrollArea>

      {paginationSlot}
      {dialogsSlot}
    </div>
  )
})
