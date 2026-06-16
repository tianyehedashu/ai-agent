import { describe, expect, it } from 'vitest'

import {
  credentialFilterOptions,
  memberFilterOptionsFromPlatformUsers,
  mergeProviderFilterOptions,
  modelFilterOptionsForStats,
  modelOptionValuesFromModels,
  providerFilterOptionsFromUsageItems,
  usageLogsShowCaller,
  usageStatsShowMemberFilter,
} from '@/features/gateway-usage/usage-stats-filter-catalog'

describe('usageLogsShowCaller', () => {
  it('hides caller on user aggregation', () => {
    expect(usageLogsShowCaller('user', false)).toBe(false)
    expect(usageLogsShowCaller('user', true)).toBe(false)
  })

  it('shows caller on platform regardless of team kind', () => {
    expect(usageLogsShowCaller('platform', true)).toBe(true)
    expect(usageLogsShowCaller('platform', false)).toBe(true)
  })

  it('shows caller on workspace shared team only', () => {
    expect(usageLogsShowCaller('workspace', false)).toBe(true)
    expect(usageLogsShowCaller('workspace', true)).toBe(false)
  })
})

describe('usageStatsShowMemberFilter', () => {
  it('hides member filter on user aggregation', () => {
    expect(usageStatsShowMemberFilter('user')).toBe(false)
  })

  it('shows member filter on workspace and platform', () => {
    expect(usageStatsShowMemberFilter('workspace')).toBe(true)
    expect(usageStatsShowMemberFilter('platform')).toBe(true)
  })
})

describe('modelOptionValuesFromModels', () => {
  it('includes name and real_model', () => {
    const values = modelOptionValuesFromModels([
      {
        name: 'gpt-4',
        real_model: 'openai/gpt-4',
        provider: 'openai',
      } as never,
    ])
    expect(values).toEqual(['gpt-4', 'openai/gpt-4'])
  })
})

describe('memberFilterOptionsFromPlatformUsers', () => {
  it('maps platform users to filter options', () => {
    const options = memberFilterOptionsFromPlatformUsers([
      {
        id: 'u1',
        email: 'a@b.com',
        name: 'Alice',
        role: 'user',
        is_active: true,
        is_verified: true,
        status: 'active',
        created_at: '',
        vendor_creator_id: null,
        avatar_url: null,
      },
    ])
    expect(options).toEqual([{ value: 'u1', label: 'Alice', meta: 'a@b.com' }])
  })
})

describe('modelFilterOptionsForStats', () => {
  it('shows real_model as meta when it differs from name', () => {
    const options = modelFilterOptionsForStats([
      {
        name: 'my-gpt',
        real_model: 'openai/gpt-4o',
        provider: 'openai',
      },
    ])
    expect(options).toHaveLength(2)
    expect(options[0]).toMatchObject({ value: 'my-gpt', label: 'my-gpt', meta: 'openai/gpt-4o' })
    expect(options[1]).toMatchObject({
      value: 'openai/gpt-4o',
      label: 'openai/gpt-4o',
      meta: 'my-gpt',
    })
  })
})

describe('mergeProviderFilterOptions', () => {
  it('merges usage and registry without duplicate values', () => {
    const merged = mergeProviderFilterOptions(
      [{ value: 'openai', label: 'OpenAI' }],
      [{ value: 'volcengine', label: 'Volcengine' }],
      [{ value: 'openai', label: 'OpenAI (profile)' }]
    )
    expect(merged.map((o) => o.value).sort()).toEqual(['openai', 'volcengine'])
  })
})

describe('providerFilterOptionsFromUsageItems', () => {
  it('maps statistics group_by=provider rows', () => {
    const options = providerFilterOptionsFromUsageItems([
      { group_key: 'anthropic', label: 'Anthropic' },
      { group_key: 'openai', label: 'OpenAI' },
    ])
    expect(options).toHaveLength(2)
    expect(options[0]?.value).toBe('anthropic')
  })
})

describe('credentialFilterOptions', () => {
  it('maps credential id and name', () => {
    const options = credentialFilterOptions([
      { id: 'c1', name: 'Key A', provider: 'openai' } as never,
    ])
    expect(options[0]?.value).toBe('c1')
    expect(options[0]?.label).toBe('Key A')
  })
})
