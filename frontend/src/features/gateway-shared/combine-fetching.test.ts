import { describe, expect, it } from 'vitest'

import { combineFetching } from './combine-fetching'

describe('combineFetching', () => {
  it('returns false when all flags are false', () => {
    expect(combineFetching(false, false)).toBe(false)
  })

  it('returns true when any flag is true', () => {
    expect(combineFetching(false, true, false)).toBe(true)
    expect(combineFetching(true)).toBe(true)
  })
})
