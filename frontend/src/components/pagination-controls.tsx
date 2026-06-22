import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export interface PaginationControlsProps {
  page: number
  page_size: number
  total: number
  has_next: boolean
  has_prev: boolean
  /** false 时 total 仅为下界，不展示「共 N 条 / 总页数」 */
  total_exact?: boolean
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
  total_exact = true,
  onPageChange,
  className,
}: PaginationControlsProps): React.JSX.Element | null {
  if (total <= 0 && total_exact) return null

  const start = total > 0 ? (page - 1) * page_size + 1 : 0
  const end = total > 0 ? Math.min(page * page_size, total) : 0
  const rangeLabel =
    total > 0
      ? total_exact
        ? `第 ${String(start)}–${String(end)} 条，共 ${String(total)} 条 · 第 ${String(page)}/${String(totalPages(total, page_size))} 页`
        : `第 ${String(start)}–${String(end)} 条${has_next ? '（还有更多）' : ''} · 第 ${String(page)} 页`
      : '暂无数据'

  return (
    <div
      className={cn(
        'flex flex-wrap items-center justify-between gap-2 text-sm text-muted-foreground',
        className
      )}
    >
      <span className="tabular-nums">{rangeLabel}</span>
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
