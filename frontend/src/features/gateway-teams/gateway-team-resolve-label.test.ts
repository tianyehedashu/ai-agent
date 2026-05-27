import { describe, expect, it } from 'vitest'

import { resolveTeamLabelFromMap } from './gateway-team-resolve-label'

describe('resolveTeamLabelFromMap', () => {
  it('returns mapped label when present', () => {
    const map = new Map([['team-uuid-1', '研发']])
    expect(resolveTeamLabelFromMap(map, 'team-uuid-1')).toBe('研发')
  })

  it('falls back to short id prefix', () => {
    expect(resolveTeamLabelFromMap(new Map(), 'b283de28-8c47-4f95-bdbd-3e0672222024')).toBe(
      'b283de28…'
    )
  })
})
