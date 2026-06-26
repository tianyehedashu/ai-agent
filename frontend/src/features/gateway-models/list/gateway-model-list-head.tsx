/**
 * 模型列表表头（扁平原属列 / 多列布局）。
 */

import type React from 'react'

import { cn } from '@/lib/utils'

import { useModelListColumnsLayout } from './model-list-columns-layout'

import type { ModelListColumnKey } from './model-list-column-layout'

export interface GatewayModelListHeadProps {
  showAffiliationColumn?: boolean
  showBatchSelect?: boolean
  showTrailing?: boolean
  layout?: 'stacked' | 'compact' | 'columns'
}

interface ResizableColumnHeaderProps {
  columnKey: ModelListColumnKey
  children: React.ReactNode
  className?: string
}

function ResizableColumnHeader({
  columnKey,
  children,
  className,
}: ResizableColumnHeaderProps): React.JSX.Element {
  const { startResize, resetColumn } = useModelListColumnsLayout()

  return (
    <div className={cn('relative min-w-0 select-none', className)}>
      <div className="px-3 py-2.5 pr-4 text-[11px] font-medium tracking-wide text-muted-foreground">
        {children}
      </div>
      <button
        type="button"
        tabIndex={-1}
        aria-label={`调整 ${typeof children === 'string' ? children : '列'} 宽度，双击恢复默认`}
        title="拖拽调整列宽，双击恢复默认"
        className={cn(
          'absolute right-0 top-0 z-20 h-full w-3 translate-x-1/2',
          'cursor-col-resize touch-none opacity-40 hover:opacity-100',
          'after:absolute after:inset-y-1 after:left-1/2 after:w-0.5 after:-translate-x-1/2 after:rounded-full after:bg-border',
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

function StaticColumnHeader({
  children,
  className,
}: {
  children: React.ReactNode
  className?: string
}): React.JSX.Element {
  return (
    <div
      className={cn(
        'px-3 py-2.5 text-[11px] font-medium tracking-wide text-muted-foreground',
        className
      )}
    >
      {children}
    </div>
  )
}

function ColumnsModelListHead({
  showAffiliationColumn,
  showBatchSelect,
  showTrailing,
}: Pick<
  GatewayModelListHeadProps,
  'showAffiliationColumn' | 'showBatchSelect' | 'showTrailing'
>): React.JSX.Element {
  const { gridTemplateColumns, tableMinWidth } = useModelListColumnsLayout()

  return (
    <div className="sticky top-0 z-10 border-b bg-muted/40 backdrop-blur-sm supports-[backdrop-filter]:bg-muted/30">
      <div
        className="grid w-full min-w-0 items-center"
        style={{
          gridTemplateColumns,
          minWidth: tableMinWidth,
        }}
      >
        {showBatchSelect ? <div className="px-2 py-2.5" aria-hidden /> : null}
        {showAffiliationColumn ? (
          <ResizableColumnHeader columnKey="affiliation">归属</ResizableColumnHeader>
        ) : null}
        <ResizableColumnHeader columnKey="invokeName">调用名</ResizableColumnHeader>
        <ResizableColumnHeader columnKey="displayName">显示名</ResizableColumnHeader>
        <ResizableColumnHeader columnKey="channel">通道</ResizableColumnHeader>
        <ResizableColumnHeader columnKey="upstream">上游</ResizableColumnHeader>
        <ResizableColumnHeader columnKey="contextWindow">上下文</ResizableColumnHeader>
        <ResizableColumnHeader columnKey="capability">能力</ResizableColumnHeader>
        <ResizableColumnHeader columnKey="credential">凭据</ResizableColumnHeader>
        <ResizableColumnHeader columnKey="status">状态</ResizableColumnHeader>
        {showTrailing ? <StaticColumnHeader className="text-right">操作</StaticColumnHeader> : null}
      </div>
    </div>
  )
}

export function GatewayModelListHead({
  showAffiliationColumn = false,
  showBatchSelect = false,
  showTrailing = false,
  layout = 'compact',
}: GatewayModelListHeadProps): React.JSX.Element {
  if (layout === 'columns') {
    return (
      <ColumnsModelListHead
        showAffiliationColumn={showAffiliationColumn}
        showBatchSelect={showBatchSelect}
        showTrailing={showTrailing}
      />
    )
  }

  return (
    <div className="sticky top-0 z-10 border-b bg-muted/30 text-xs font-medium text-muted-foreground backdrop-blur-sm supports-[backdrop-filter]:bg-muted/20">
      <div
        className={
          showBatchSelect && showTrailing
            ? 'grid grid-cols-[auto_96px_minmax(0,1fr)_auto] items-center'
            : showBatchSelect
              ? 'grid grid-cols-[auto_96px_minmax(0,1fr)] items-center'
              : showAffiliationColumn && showTrailing
                ? 'grid grid-cols-[96px_minmax(0,1fr)_auto] items-center'
                : showAffiliationColumn
                  ? 'grid grid-cols-[96px_minmax(0,1fr)] items-center'
                  : 'grid grid-cols-[minmax(0,1fr)_auto] items-center'
        }
      >
        {showBatchSelect ? <div className="px-2 py-2" aria-hidden /> : null}
        {showAffiliationColumn ? <div className="px-3 py-2">归属</div> : null}
        <div className="px-3 py-2">模型</div>
        {showTrailing ? <div className="px-3 py-2 text-right">操作</div> : null}
      </div>
    </div>
  )
}
