import { describe, expect, it } from 'vitest'

import { GATEWAY_FILTER_ALL } from './gateway-filter-combobox'
import {
  applyDrillSegmentToFilterState,
  clearDrillSegmentsFromFilterState,
  drillDownNextState,
  shouldShowBreakdownColumns,
} from './usage-stats-drill-down'

const baseFilters = {
  credentialId: GATEWAY_FILTER_ALL,
  userId: GATEWAY_FILTER_ALL,
  teamFilterId: GATEWAY_FILTER_ALL,
  model: GATEWAY_FILTER_ALL,
  provider: GATEWAY_FILTER_ALL,
  capability: GATEWAY_FILTER_ALL,
  status: GATEWAY_FILTER_ALL,
  vkeyId: GATEWAY_FILTER_ALL,
}

function expectUserDrillSegment(): NonNullable<ReturnType<typeof drillDownNextState>> {
  const next = drillDownNextState('user', 'u1', 'Alice')
  expect(next).not.toBeNull()
  if (next === null) {
    throw new Error('expected drill state')
  }
  return next
}

describe('drillDownNextState', () => {
  it('maps user row to model grouping with user_id filter', () => {
    const next = drillDownNextState('user', 'uid-1', '张三')
    expect(next).toEqual({
      segment: {
        label: '张三',
        filterKey: 'user_id',
        filterValue: 'uid-1',
        groupByAfter: 'model',
      },
      groupBy: 'model',
    })
  })

  it('returns null for empty group key', () => {
    expect(drillDownNextState('credential', '', '凭据')).toBeNull()
  })
})

describe('applyDrillSegmentToFilterState', () => {
  it('sets userId from segment', () => {
    const next = expectUserDrillSegment()
    expect(applyDrillSegmentToFilterState(baseFilters, next.segment).userId).toBe('u1')
  })
})

describe('clearDrillSegmentsFromFilterState', () => {
  it('resets drill-applied filters', () => {
    const next = expectUserDrillSegment()
    const applied = applyDrillSegmentToFilterState(baseFilters, next.segment)
    expect(clearDrillSegmentsFromFilterState(applied, [next.segment]).userId).toBe(
      GATEWAY_FILTER_ALL
    )
  })
})

describe('shouldShowBreakdownColumns', () => {
  it('hides breakdown columns when primary group is credential or model', () => {
    expect(shouldShowBreakdownColumns('user')).toBe(true)
    expect(shouldShowBreakdownColumns('credential')).toBe(false)
    expect(shouldShowBreakdownColumns('model')).toBe(false)
  })
})
