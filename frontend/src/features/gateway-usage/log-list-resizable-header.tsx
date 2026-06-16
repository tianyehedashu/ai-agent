import type { ReactNode } from 'react'

import type { LogListColumnKey } from '@/features/gateway-usage/log-list-column-layout'
import { cn } from '@/lib/utils'

export interface LogListResizableHeaderProps {
  columnKey: LogListColumnKey
  children: ReactNode
  className?: string
  startResize: (key: LogListColumnKey, clientX: number) => void
  resetColumn: (key: LogListColumnKey) => void
}

export function LogListResizableHeader({
  columnKey,
  children,
  className,
  startResize,
  resetColumn,
}: LogListResizableHeaderProps): React.JSX.Element {
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
