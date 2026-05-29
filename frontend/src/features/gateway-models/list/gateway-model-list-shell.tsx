import { memo } from 'react'

import { Loader2 } from '@/lib/lucide-icons'
import { cn } from '@/lib/utils'

import type { GatewayModelListShellProps } from './types'

/**
 * 列表外壳：顶部控件 / 列表本体 / 底部分页按内容自然高度铺开，统一交给页面级单一滚动容器，
 * 不在已可滚动的页面内再嵌套固定/上限高度的滚动区，避免内容被裁切、无法滚动看全。
 */
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

      <div className="min-h-[280px]">
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
          children
        )}
      </div>

      {paginationSlot}
      {dialogsSlot}
    </div>
  )
})
