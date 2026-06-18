import { describe, expect, it } from 'vitest'

import type { EntitlementPlan } from '@/api/gateway'

import { filterActiveEntitlementPlans } from './use-keys-entitlements'

describe('filterActiveEntitlementPlans', () => {
  it('returns only plans whose valid_from has taken effect', () => {
    const now = Date.now()
    const plans: EntitlementPlan[] = [
      {
        id: '1',
        label: 'effective',
        valid_from: new Date(now - 86_400_000).toISOString(),
      } as EntitlementPlan,
      {
        id: '2',
        label: 'not-yet',
        valid_from: new Date(now + 86_400_000).toISOString(),
      } as EntitlementPlan,
    ]
    const active = filterActiveEntitlementPlans(plans)
    expect(active).toHaveLength(1)
    expect(active[0]?.label).toBe('effective')
  })
})
