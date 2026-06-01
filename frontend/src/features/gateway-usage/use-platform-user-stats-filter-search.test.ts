import { describe, expect, it } from 'vitest'

import { PLATFORM_USER_STATS_FILTER_PAGE_SIZE } from '@/features/gateway-usage/use-platform-user-stats-filter-search'

describe('PLATFORM_USER_STATS_FILTER_PAGE_SIZE', () => {
  it('caps each search request to avoid loading entire user directory', () => {
    expect(PLATFORM_USER_STATS_FILTER_PAGE_SIZE).toBeLessThanOrEqual(100)
    expect(PLATFORM_USER_STATS_FILTER_PAGE_SIZE).toBeGreaterThan(0)
  })
})
