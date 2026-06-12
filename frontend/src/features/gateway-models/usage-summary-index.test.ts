import { describe, expect, it } from 'vitest'

import { indexUsageByRouteName } from './usage-summary-index'

describe('indexUsageByRouteName', () => {
  it('indexes rows by route_name', () => {
    const map = indexUsageByRouteName([
      {
        route_name: 'team/a',
        workspace: { requests: 1, input_tokens: 0, output_tokens: 0, cost_usd: 0 },
        user: { requests: 0, input_tokens: 0, output_tokens: 0, cost_usd: 0 },
      },
    ])
    expect(map.get('team/a')?.workspace.requests).toBe(1)
    expect(map.size).toBe(1)
  })

  it('returns empty map for undefined items', () => {
    expect(indexUsageByRouteName(undefined).size).toBe(0)
  })
})
