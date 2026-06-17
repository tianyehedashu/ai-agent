import type { ReactNode } from 'react'

import type { QuotaCenterColumnKey } from '@/features/gateway-budget/quota-center-column-layout'
import { cn } from '@/lib/utils'

export interface QuotaCenterResizableHeaderProps {
  columnKey: QuotaCenterColumnKey
  children: ReactNode
  className?: string
  startResize: (key: QuotaCenterColumnKey, clientX: number) => void
  resetColumn: (key: QuotaCenterColumnKey) => void
}

export function QuotaCenterResizableHeader({
  columnKey,
  children,
  className,
  startResize,
  resetColumn,
}: QuotaCenterResizableHeaderProps): React.JSX.Element {
  const label = typeof children === 'string' ? children : '列'

  return (
    <div className={cn('relative min-w-0 select-none', className)}>
      {children}
      <button
        type="button"
        tabIndex={-1}
        aria-label={`调整 ${label} 宽度，双击恢复默认`}
        title="拖拽调整列宽，双击恢复默认"
        className={cn(
          'absolute right-0 top-0 z-20 h-full w-3 translate-x-1/2',
          'cursor-col-resize touch-none opacity-40 hover:opacity-100',
          'after:absolute after:inset-y-0 after:left-1/2 after:w-0.5 after:-translate-x-1/2 after:rounded-full after:bg-border',
          'hover:after:bg-primary/70 active:after:bg-primary'
        )}
        onMouseDown={(event) => {
          event.preventDefault()
          event.stopPropagation()
          startResize(columnKey, event.clientX)
        }}
        onDoubleClick={(event) => {
          event.preventDefault()
          event.stopPropagation()
          resetColumn(columnKey)
        }}
      />
    </div>
  )
}
