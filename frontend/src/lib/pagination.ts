import type { PaginatedList } from '@/types'

/** 与后端 `libs.api.pagination.MAX_PAGE_SIZE` 一致 */
export const MAX_PAGE_SIZE = 200

export const DEFAULT_PAGE_SIZE = 20

/** ``/ids`` 类 endpoint 命中 max_ids 上限时的用户提示 */
export const IDS_TRUNCATION_HINT = '匹配结果过多，仅返回了前 5000 条。请缩小筛选范围后重试。'

/** 当 ``truncated === true`` 时调用 notify 并返回 true（表示应中止批量操作）。 */
export function warnIfIdsTruncated(
  truncated: boolean | undefined,
  notify: (message: string) => void
): boolean {
  if (!truncated) return false
  notify(IDS_TRUNCATION_HINT)
  return true
}

export function totalPages(total: number, pageSize: number): number {
  if (total <= 0) return 1
  return Math.max(1, Math.ceil(total / pageSize))
}

/**
 * 按页拉取直至 `has_next === false`。
 * 仅用于批量操作 / 必须全量的场景；常规定制列表请用服务端分页。
 */
export async function fetchAllPaginatedPages<T>(
  fetchPage: (page: number, page_size: number) => Promise<PaginatedList<T>>,
  pageSize: number = MAX_PAGE_SIZE
): Promise<T[]> {
  const all: T[] = []
  let page = 1
  for (;;) {
    const res = await fetchPage(page, pageSize)
    all.push(...res.items)
    if (!res.has_next) break
    page += 1
  }
  return all
}
