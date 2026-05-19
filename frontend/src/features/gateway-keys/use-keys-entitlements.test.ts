import { describe, expect, it } from 'vitest'

import type { EntitlementPlan } from '@/api/gateway'

import { filterActiveEntitlementPlans } from './use-keys-entitlements'

describe('filterActiveEntitlementPlans', () => {
  it('returns only active plans within valid window', () => {
    const now = Date.now()
    const plans: EntitlementPlan[] = [
      {
        id: '1',
        label: 'active',
        is_active: true,
        valid_from: new Date(now - 86_400_000).toISOString(),
        valid_until: new Date(now + 86_400_000).toISOString(),
      } as EntitlementPlan,
      {
        id: '2',
        label: 'expired',
        is_active: true,
        valid_from: new Date(now - 172_800_000).toISOString(),
        valid_until: new Date(now - 86_400_000).toISOString(),
      } as EntitlementPlan,
    ]
    const active = filterActiveEntitlementPlans(plans)
    expect(active).toHaveLength(1)
    expect(active[0]?.label).toBe('active')
  })
})
