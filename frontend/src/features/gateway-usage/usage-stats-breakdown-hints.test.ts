import { describe, expect, it } from 'vitest'

import { credentialBreakdownFooterHints } from './usage-stats-breakdown-hints'

describe('credentialBreakdownFooterHints', () => {
  const base = {
    parent_group_by: 'user' as const,
    parent_group_key: 'u1',
    breakdown_by: 'credential' as const,
    parent_requests: 100,
  }

  it('reports unassigned requests separately from top_n cap', () => {
    const hints = credentialBreakdownFooterHints(
      {
        ...base,
        items: Array.from({ length: 32 }, (_, index) => ({
          group_key: `c${index.toString()}`,
          label: `cred-${index.toString()}`,
          requests: 2,
          share: 0.02,
        })),
      },
      32
    )
    expect(hints).toContain('36 次请求未关联凭据')
    expect(hints.some((hint) => hint.includes('前 32 个凭据'))).toBe(true)
  })

  it('returns empty when fully listed with no cap', () => {
    expect(
      credentialBreakdownFooterHints(
        {
          ...base,
          parent_requests: 10,
          items: [{ group_key: 'c1', label: 'A', requests: 10, share: 1 }],
        },
        32
      )
    ).toEqual([])
  })
})
