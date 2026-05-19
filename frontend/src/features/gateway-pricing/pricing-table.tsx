import type React from 'react'

import { Button } from '@/components/ui/button'

export interface PricingTableColumn {
  key: string
  label: string
  className?: string
}

export function PricingTable({
  columns,
  children,
  loading,
  error,
  empty,
  onRetry,
}: Readonly<{
  columns: readonly PricingTableColumn[]
  children: React.ReactNode
  loading?: boolean
  error?: boolean
  empty?: boolean
  onRetry?: () => void
}>): React.JSX.Element {
  if (loading) {
    return <p className="text-sm text-muted-foreground">加载中...</p>
  }

  if (error) {
    return (
      <div className="rounded-md border border-destructive/30 bg-destructive/5 p-4 text-sm">
        <p className="font-medium text-destructive">定价数据加载失败</p>
        <p className="mt-1 text-muted-foreground">请稍后重试，或检查当前账号权限。</p>
        {onRetry ? (
          <Button type="button" variant="outline" size="sm" className="mt-3" onClick={onRetry}>
            重试
          </Button>
        ) : null}
      </div>
    )
  }

  if (empty) {
    return (
      <div className="rounded-md border border-dashed p-6 text-sm text-muted-foreground">
        暂无定价数据。
      </div>
    )
  }

  return (
    <div className="overflow-x-auto rounded-md border">
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-muted/40 text-left text-muted-foreground">
          <tr>
            {columns.map((column) => (
              <th key={column.key} className={column.className ?? 'px-3 py-2'}>
                {column.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  )
}
