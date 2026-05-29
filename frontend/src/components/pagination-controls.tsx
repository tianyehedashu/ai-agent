import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export interface PaginationControlsProps {
  page: number
  page_size: number
  total: number
  has_next: boolean
  has_prev: boolean
  onPageChange: (page: number) => void
  className?: string
}

function totalPages(total: number, pageSize: number): number {
  if (total <= 0) return 1
  return Math.max(1, Math.ceil(total / pageSize))
}

/** 与后端 PaginatedListResponse 对齐的分页控件 */
export function PaginationControls({
  page,
  page_size,
  total,
  has_next,
  has_prev,
  onPageChange,
  className,
}: PaginationControlsProps): React.JSX.Element | null {
  if (total <= 0) return null

  const pages = totalPages(total, page_size)
  const start = (page - 1) * page_size + 1
  const end = Math.min(page * page_size, total)

  return (
    <div
      className={cn(
        'flex flex-wrap items-center justify-between gap-2 text-sm text-muted-foreground',
        className
      )}
    >
      <span className="tabular-nums">
        第 {start}–{end} 条，共 {total} 条 · 第 {page}/{pages} 页
      </span>
      <div className="flex items-center gap-1">
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-8"
          disabled={!has_prev}
          onClick={() => {
            onPageChange(page - 1)
          }}
        >
          上一页
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-8"
          disabled={!has_next}
          onClick={() => {
            onPageChange(page + 1)
          }}
        >
          下一页
        </Button>
      </div>
    </div>
  )
}
