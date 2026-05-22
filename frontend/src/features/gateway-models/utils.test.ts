import { describe, expect, it } from 'vitest'

import type { GatewayModel, GatewayRoute } from '@/api/gateway'

import {
  classifyFailureReason,
  enabledGatewayModels,
  excludeModelsFromList,
  formatUsageLine,
  matchesHealthFilter,
  moveOrderedModelList,
  pickInspectorModelId,
  routesReferencingModel,
  filterTestableConnectivityModels,
  filterProxyCallableModels,
  filterRegistryRequestableModels,
  isProxyCallableModel,
  isRegistryRequestableModel,
  runBatchConnectivityTests,
  runWithConcurrency,
  resolveTeamModelsRegistryScope,
  resolvePlaygroundTeamRegistryScope,
  playgroundTeamModelsQueryKey,
  stringArraysEqual,
  summarizeHealth,
  toggleModelSet,
  toggleOrderedModelList,
} from './utils'

import type { HealthFilter } from './constants'

function model(
  partial: Partial<GatewayModel> & Pick<GatewayModel, 'last_test_status'>
): GatewayModel {
  return {
    id: '1',
    tenant_id: partial.tenant_id ?? partial.team_id ?? 't',
    team_id: partial.team_id ?? 't',
    name: 'p/m',
    capability: 'chat',
    real_model: 'm',
    credential_id: 'c',
    provider: 'openai',
    weight: 1,
    rpm_limit: null,
    tpm_limit: null,
    enabled: true,
    last_tested_at: null,
    last_test_reason: null,
    created_at: '',
    ...partial,
  }
}

describe('isRegistryRequestableModel', () => {
  it('allows enabled non-failed models', () => {
    expect(isRegistryRequestableModel(model({ enabled: true, last_test_status: 'success' }))).toBe(
      true
    )
    expect(isRegistryRequestableModel(model({ enabled: true, last_test_status: null }))).toBe(true)
  })

  it('rejects disabled or failed models', () => {
    expect(isRegistryRequestableModel(model({ enabled: false, last_test_status: 'success' }))).toBe(
      false
    )
    expect(isRegistryRequestableModel(model({ enabled: true, last_test_status: 'failed' }))).toBe(
      false
    )
  })

  it('ignores entitlement_status', () => {
    expect(
      isRegistryRequestableModel(
        model({ enabled: true, last_test_status: 'success', entitlement_status: 'exhausted' })
      )
    ).toBe(true)
  })
})

describe('isProxyCallableModel', () => {
  it('rejects exhausted or expired entitlements', () => {
    expect(
      isProxyCallableModel(
        model({ enabled: true, last_test_status: 'success', entitlement_status: 'exhausted' })
      )
    ).toBe(false)
    expect(
      isProxyCallableModel(
        model({ enabled: true, last_test_status: 'success', entitlement_status: 'expired' })
      )
    ).toBe(false)
  })

  it('allows active entitlement when registry requestable', () => {
    expect(
      isProxyCallableModel(
        model({ enabled: true, last_test_status: 'success', entitlement_status: 'active' })
      )
    ).toBe(true)
  })
})

describe('filterRegistryRequestableModels', () => {
  it('returns only registry-requestable models', () => {
    const items = [
      model({ id: 'ok', enabled: true, last_test_status: 'success' }),
      model({ id: 'fail', enabled: true, last_test_status: 'failed' }),
      model({ id: 'off', enabled: false, last_test_status: 'success' }),
    ]
    expect(filterRegistryRequestableModels(items).map((m) => m.id)).toEqual(['ok'])
  })
})

describe('filterProxyCallableModels', () => {
  it('excludes entitlement-blocked models', () => {
    const items = [
      model({ id: 'ok', enabled: true, last_test_status: 'success', entitlement_status: 'active' }),
      model({
        id: 'ex',
        enabled: true,
        last_test_status: 'success',
        entitlement_status: 'exhausted',
      }),
    ]
    expect(filterProxyCallableModels(items).map((m) => m.id)).toEqual(['ok'])
  })
})

describe('pickInspectorModelId', () => {
  const candidates = [
    model({ id: 'a', enabled: false, last_test_status: 'success' }),
    model({ id: 'b', enabled: true, last_test_status: 'failed' }),
    model({ id: 'c', enabled: true, last_test_status: 'success' }),
    model({ id: 'd', enabled: true, last_test_status: null }),
  ]

  it('prefers deep link id when visible', () => {
    expect(pickInspectorModelId(candidates, null, 'b')).toBe('b')
  })

  it('keeps current selection when still visible', () => {
    expect(pickInspectorModelId(candidates, 'd')).toBe('d')
  })

  it('picks enabled model with successful health when no selection', () => {
    expect(pickInspectorModelId(candidates, null)).toBe('c')
  })

  it('returns null when list is empty', () => {
    expect(pickInspectorModelId([], null)).toBeNull()
  })
})

describe('classifyFailureReason', () => {
  it('maps quota errors', () => {
    expect(classifyFailureReason('free tier exhausted')).toBe('额度或配额')
  })

  it('maps auth errors', () => {
    expect(classifyFailureReason('401 unauthorized api key')).toBe('凭据无效')
  })

  it('returns default for empty', () => {
    expect(classifyFailureReason(null)).toBe('连接失败')
  })
})

describe('matchesHealthFilter', () => {
  it('filters failed models', () => {
    const m = model({ last_test_status: 'failed' })
    expect(matchesHealthFilter(m, 'failed')).toBe(true)
    expect(matchesHealthFilter(m, 'success')).toBe(false)
  })

  it('allows all when filter is all', () => {
    const m = model({ last_test_status: null })
    expect(matchesHealthFilter(m, 'all' as HealthFilter)).toBe(true)
  })
})

describe('formatUsageLine', () => {
  it('formats 24h label', () => {
    expect(formatUsageLine(1, 10, 100, 0.01)).toContain('24h')
    expect(formatUsageLine(1, 10, 100, 0.01)).toContain('10 次')
  })
})

describe('routesReferencingModel', () => {
  const routes: GatewayRoute[] = [
    {
      id: 'r1',
      tenant_id: 't',
      team_id: 't',
      virtual_model: 'v1',
      primary_models: ['a/b'],
      fallbacks_general: [],
      fallbacks_content_policy: [],
      fallbacks_context_window: [],
      strategy: 'simple-shuffle',
      enabled: true,
    },
  ]

  it('finds primary reference', () => {
    expect(routesReferencingModel(routes, 'a/b')).toHaveLength(1)
    expect(routesReferencingModel(routes, 'other')).toHaveLength(0)
  })
})

describe('summarizeHealth', () => {
  it('counts statuses', () => {
    const summary = summarizeHealth([
      model({ last_test_status: 'success' }),
      model({ id: '2', last_test_status: 'failed' }),
      model({ id: '3', last_test_status: null }),
    ])
    expect(summary).toEqual({ total: 3, success: 1, failed: 1, unknown: 1 })
  })
})

describe('enabledGatewayModels', () => {
  it('returns only enabled models', () => {
    const items = enabledGatewayModels([
      model({ enabled: true, last_test_status: null }),
      model({ id: '2', enabled: false, last_test_status: null }),
      model({ id: '3', enabled: true, last_test_status: null, name: 'b/c' }),
    ])
    expect(items.map((m) => m.name)).toEqual(['p/m', 'b/c'])
  })
})

describe('toggleOrderedModelList', () => {
  it('appends on check and removes on uncheck', () => {
    expect(toggleOrderedModelList([], 'a', true)).toEqual(['a'])
    expect(toggleOrderedModelList(['a'], 'b', true)).toEqual(['a', 'b'])
    expect(toggleOrderedModelList(['a', 'b'], 'a', false)).toEqual(['b'])
  })
})

describe('moveOrderedModelList', () => {
  it('swaps adjacent items', () => {
    expect(moveOrderedModelList(['a', 'b', 'c'], 1, -1)).toEqual(['b', 'a', 'c'])
    expect(moveOrderedModelList(['a', 'b', 'c'], 0, -1)).toEqual(['a', 'b', 'c'])
  })
})

describe('toggleModelSet', () => {
  it('toggles membership without order semantics', () => {
    expect(toggleModelSet(['x'], 'y', true)).toEqual(['x', 'y'])
    expect(toggleModelSet(['x', 'y'], 'x', false)).toEqual(['y'])
  })
})

describe('excludeModelsFromList', () => {
  it('removes names present in exclude list', () => {
    expect(excludeModelsFromList(['a', 'b', 'c'], ['b'])).toEqual(['a', 'c'])
    expect(excludeModelsFromList(['a'], [])).toEqual(['a'])
  })
})

describe('stringArraysEqual', () => {
  it('compares order-sensitive', () => {
    expect(stringArraysEqual(['a', 'b'], ['a', 'b'])).toBe(true)
    expect(stringArraysEqual(['a', 'b'], ['b', 'a'])).toBe(false)
  })
})

describe('filterTestableConnectivityModels', () => {
  it('keeps only chat embedding image capabilities', () => {
    const items = [
      { id: '1', capability: 'chat', last_test_status: null },
      { id: '2', capability: 'video_generation', last_test_status: null },
      { id: '3', capability: 'embedding', last_test_status: null },
    ]
    expect(filterTestableConnectivityModels(items).map((m) => m.id)).toEqual(['1', '3'])
  })
})

describe('runBatchConnectivityTests', () => {
  it('invokes testById only for testable models', async () => {
    const tested: string[] = []
    await runBatchConnectivityTests(
      [
        { id: 'a', capability: 'chat', last_test_status: null },
        { id: 'b', capability: 'video_generation', last_test_status: null },
      ],
      (id) => {
        tested.push(id)
        return Promise.resolve()
      }
    )
    expect(tested.sort()).toEqual(['a'])
  })
})

describe('runWithConcurrency', () => {
  it('runs all items with bounded concurrency', async () => {
    const order: number[] = []
    let inFlight = 0
    let maxInFlight = 0
    const items = [0, 1, 2, 3, 4]
    await runWithConcurrency(items, 2, async (n) => {
      inFlight += 1
      maxInFlight = Math.max(maxInFlight, inFlight)
      order.push(n)
      await new Promise((r) => setTimeout(r, 5))
      inFlight -= 1
    })
    expect(order.sort((a, b) => a - b)).toEqual(items)
    expect(maxInFlight).toBeLessThanOrEqual(2)
    expect(maxInFlight).toBeGreaterThanOrEqual(1)
  })
})

describe('resolveTeamModelsRegistryScope', () => {
  it('uses team scope on shared tab without credential filter', () => {
    expect(resolveTeamModelsRegistryScope('team', '')).toBe('team')
  })

  it('uses callable scope when filtering by credential', () => {
    expect(resolveTeamModelsRegistryScope('team', 'cred-1')).toBe('callable')
  })

  it('uses system scope on system tab', () => {
    expect(resolveTeamModelsRegistryScope('system', '')).toBe('system')
  })
})

describe('resolvePlaygroundTeamRegistryScope', () => {
  it('uses requestable without credential filter', () => {
    expect(resolvePlaygroundTeamRegistryScope('')).toBe('requestable')
  })

  it('uses callable when filtering by credential', () => {
    expect(resolvePlaygroundTeamRegistryScope('cred-1')).toBe('callable')
  })
})

describe('playgroundTeamModelsQueryKey', () => {
  it('switches scope in query key when credential filter is set', () => {
    expect(playgroundTeamModelsQueryKey('team-1', '')).toEqual([
      'gateway',
      'models',
      'team-1',
      'requestable',
      '',
      '',
    ])
    expect(playgroundTeamModelsQueryKey('team-1', 'cred-1')).toEqual([
      'gateway',
      'models',
      'team-1',
      'callable',
      '',
      'cred-1',
    ])
  })
})
