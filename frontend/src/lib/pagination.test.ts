import { describe, expect, it, vi } from 'vitest'

import {
  DEFAULT_PAGE_SIZE,
  IDS_TRUNCATION_HINT,
  MAX_PAGE_SIZE,
  fetchAllPaginatedPages,
  totalPages,
  warnIfIdsTruncated,
} from './pagination'

describe('totalPages', () => {
  it('returns 1 for empty total', () => {
    expect(totalPages(0, 20)).toBe(1)
  })

  it('ceil-divides total by page size', () => {
    expect(totalPages(21, 20)).toBe(2)
    expect(totalPages(40, 20)).toBe(2)
  })
})

describe('fetchAllPaginatedPages', () => {
  it('stops when has_next is false', async () => {
    const fetchPage = vi
      .fn()
      .mockResolvedValueOnce({
        items: [1, 2],
        total: 3,
        page: 1,
        page_size: 2,
        has_next: true,
        has_prev: false,
      })
      .mockResolvedValueOnce({
        items: [3],
        total: 3,
        page: 2,
        page_size: 2,
        has_next: false,
        has_prev: true,
      })

    const all = await fetchAllPaginatedPages(fetchPage, 2)

    expect(all).toEqual([1, 2, 3])
    expect(fetchPage).toHaveBeenCalledTimes(2)
    expect(fetchPage).toHaveBeenNthCalledWith(1, 1, 2)
    expect(fetchPage).toHaveBeenNthCalledWith(2, 2, 2)
  })
})

describe('pagination constants', () => {
  it('matches backend defaults', () => {
    expect(DEFAULT_PAGE_SIZE).toBe(20)
    expect(MAX_PAGE_SIZE).toBe(200)
  })
})

describe('warnIfIdsTruncated', () => {
  it('notifies and returns true when truncated', () => {
    const notify = vi.fn()
    expect(warnIfIdsTruncated(true, notify)).toBe(true)
    expect(notify).toHaveBeenCalledWith(IDS_TRUNCATION_HINT)
  })

  it('returns false when not truncated', () => {
    const notify = vi.fn()
    expect(warnIfIdsTruncated(false, notify)).toBe(false)
    expect(notify).not.toHaveBeenCalled()
  })
})
