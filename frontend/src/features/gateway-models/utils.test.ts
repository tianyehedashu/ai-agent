import { QueryClient } from '@tanstack/react-query'
import { describe, expect, it } from 'vitest'

import type { GatewayModel, GatewayModelTestResult, GatewayRoute } from '@/api/gateway'

import {
  batchConnectivityIncludesVideoGeneration,
  classifyFailureReason,
  connectivityFieldsFromTestResult,
  createBatchConnectivityCachePatcher,
  enabledGatewayModels,
  excludeModelsFromList,
  formatUsageLine,
  matchesHealthFilter,
  moveOrderedModelList,
  patchModelConnectivityInCache,
  pickInspectorModelId,
  routesReferencingModel,
  filterTestableConnectivityModels,
  filterUntestedConnectivityModels,
  filterManageableTestableModels,
  filterProxyCallableModels,
  filterRegistryRequestableModels,
  groupModelsByTeamId,
  resolveGatewayModelTeamId,
  runChunkedBatchDeleteByTeam,
  runChunkedBatchResyncByTeam,
  createManagedTeamsTestById,
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
  type ModelWithConnectivityStatus,
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

  it('maps unsupported probe capability', () => {
    expect(classifyFailureReason('capability=moderation 暂不支持连通性测试')).toBe('不支持探活')
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
  it('keeps chat, embedding, image, and video_generation capabilities', () => {
    const items = [
      { id: '1', capability: 'chat', last_test_status: null },
      { id: '2', capability: 'video_generation', last_test_status: null },
      { id: '3', capability: 'embedding', last_test_status: null },
      { id: '4', capability: 'moderation', last_test_status: null },
    ]
    expect(filterTestableConnectivityModels(items).map((m) => m.id)).toEqual(['1', '2', '3'])
  })
})

describe('filterUntestedConnectivityModels', () => {
  it('returns only testable models with unknown health', () => {
    const items: ModelWithConnectivityStatus[] = [
      { id: 'ok', capability: 'chat', last_test_status: null },
      { id: 'tested', capability: 'chat', last_test_status: 'success' },
      { id: 'failed', capability: 'chat', last_test_status: 'failed' },
      { id: 'non-testable', capability: 'moderation', last_test_status: null },
    ]
    expect(filterUntestedConnectivityModels(items).map((m) => m.id)).toEqual(['ok'])
  })
})

describe('runBatchConnectivityTests', () => {
  const fullTestResult = {
    success: true,
    message: 'ok',
    model: 'gpt-4',
    status: 'success' as const,
    tested_at: '2026-01-01T00:00:00Z',
    reason: null,
  }

  it('invokes testById only for testable models', async () => {
    const tested: string[] = []
    const failed = await runBatchConnectivityTests(
      [
        { id: 'a', capability: 'chat', last_test_status: null },
        { id: 'b', capability: 'video_generation', last_test_status: null },
        { id: 'c', capability: 'moderation', last_test_status: null },
      ],
      (id) => {
        tested.push(id)
        return Promise.resolve({ success: true })
      }
    )
    expect(tested.sort()).toEqual(['a', 'b'])
    expect(failed).toEqual([])
  })

  it('collects failed ids from unsuccessful responses and errors', async () => {
    const failed = await runBatchConnectivityTests(
      [
        { id: 'ok', capability: 'chat', last_test_status: null },
        { id: 'bad', capability: 'chat', last_test_status: null },
        { id: 'err', capability: 'embedding', last_test_status: null },
      ],
      (id) => {
        if (id === 'bad') return Promise.resolve({ success: false })
        if (id === 'err') return Promise.reject(new Error('network'))
        return Promise.resolve({ success: true })
      }
    )
    expect(failed.sort()).toEqual(['bad', 'err'])
  })

  it('calls onItemComplete for each successful API response', async () => {
    const completed: string[] = []
    await runBatchConnectivityTests(
      [{ id: 'a', capability: 'chat', last_test_status: null }],
      () => Promise.resolve(fullTestResult),
      {
        onItemComplete: (id, result) => {
          completed.push(id)
          expect(result).toEqual(fullTestResult)
        },
      }
    )
    expect(completed).toEqual(['a'])
  })

  it('skips onItemComplete when API throws', async () => {
    const completed: string[] = []
    await runBatchConnectivityTests(
      [{ id: 'a', capability: 'chat', last_test_status: null }],
      () => Promise.reject(new Error('network')),
      {
        onItemComplete: (id) => {
          completed.push(id)
        },
      }
    )
    expect(completed).toEqual([])
  })
})

describe('connectivityFieldsFromTestResult', () => {
  it('maps success response', () => {
    expect(
      connectivityFieldsFromTestResult({
        success: true,
        message: 'ok',
        model: 'gpt-4',
        status: 'success',
        tested_at: '2026-01-01T00:00:00Z',
        reason: null,
      })
    ).toEqual({
      last_test_status: 'success',
      last_tested_at: '2026-01-01T00:00:00Z',
      last_test_reason: null,
    })
  })

  it('maps failed response', () => {
    expect(
      connectivityFieldsFromTestResult({
        success: false,
        message: 'fail',
        model: 'gpt-4',
        status: 'failed',
        tested_at: '2026-01-01T00:00:00Z',
        reason: 'timeout',
      })
    ).toEqual({
      last_test_status: 'failed',
      last_tested_at: '2026-01-01T00:00:00Z',
      last_test_reason: 'timeout',
    })
  })
})

describe('patchModelConnectivityInCache', () => {
  it('patches paginated team list cache envelope', () => {
    const queryClient = new QueryClient()
    const key = ['gateway', 'models', 'team-1', 'team', '', '', 1, 20, '', 'all'] as const
    queryClient.setQueryData(key, {
      items: [
        { id: 'a', last_test_status: null, last_tested_at: null, last_test_reason: null },
        { id: 'b', last_test_status: null, last_tested_at: null, last_test_reason: null },
      ],
      total: 2,
      page: 1,
      page_size: 20,
      has_next: false,
      has_prev: false,
    })
    patchModelConnectivityInCache(
      queryClient,
      'b',
      {
        last_test_status: 'success',
        last_tested_at: '2026-01-01T00:00:00Z',
        last_test_reason: null,
      },
      'team'
    )
    const data = queryClient.getQueryData<{
      items: Array<{ id: string; last_test_status: string | null }>
    }>(key)
    expect(data?.items[0]?.last_test_status).toBe(null)
    expect(data?.items[1]?.last_test_status).toBe('success')
  })

  it('patches only matching model in team list cache', () => {
    const queryClient = new QueryClient()
    const key = ['gateway', 'models', 'team-1', 'team', '', ''] as const
    queryClient.setQueryData(key, [
      { id: 'a', last_test_status: null, last_tested_at: null, last_test_reason: null },
      { id: 'b', last_test_status: null, last_tested_at: null, last_test_reason: null },
    ])
    patchModelConnectivityInCache(
      queryClient,
      'b',
      {
        last_test_status: 'success',
        last_tested_at: '2026-01-01T00:00:00Z',
        last_test_reason: null,
      },
      'team'
    )
    const data = queryClient.getQueryData<
      Array<{
        id: string
        last_test_status: string | null
      }>
    >(key)
    expect(data?.[0]?.last_test_status).toBe(null)
    expect(data?.[1]?.last_test_status).toBe('success')
  })

  it('patches personal model list cache', () => {
    const queryClient = new QueryClient()
    const key = ['gateway', 'my-models', 'all'] as const
    queryClient.setQueryData(key, [
      { id: 'x', last_test_status: null, last_tested_at: null, last_test_reason: null },
    ])
    patchModelConnectivityInCache(
      queryClient,
      'x',
      {
        last_test_status: 'failed',
        last_tested_at: '2026-01-02T00:00:00Z',
        last_test_reason: 'timeout',
      },
      'personal'
    )
    const data = queryClient.getQueryData<
      Array<{
        id: string
        last_test_status: string | null
        last_test_reason: string | null
      }>
    >(key)
    expect(data?.[0]?.last_test_status).toBe('failed')
    expect(data?.[0]?.last_test_reason).toBe('timeout')
  })

  it('leaves non-model-list cache entries unchanged', () => {
    const queryClient = new QueryClient()
    const key = ['gateway', 'models', 'usage-summary', 'team-1', '', 7] as const
    const summary = { items: [] }
    queryClient.setQueryData(key, summary)
    patchModelConnectivityInCache(
      queryClient,
      'b',
      {
        last_test_status: 'success',
        last_tested_at: '2026-01-01T00:00:00Z',
        last_test_reason: null,
      },
      'team'
    )
    expect(queryClient.getQueryData(key)).toEqual(summary)
  })

  it('createBatchConnectivityCachePatcher maps test result into list cache', () => {
    const queryClient = new QueryClient()
    const key = ['gateway', 'my-models'] as const
    queryClient.setQueryData(key, [
      { id: 'm1', last_test_status: null, last_tested_at: null, last_test_reason: null },
    ])
    const patch = createBatchConnectivityCachePatcher(queryClient, 'personal')
    patch('m1', {
      success: true,
      message: 'ok',
      model: 'gpt-4',
      status: 'success',
      tested_at: '2026-03-01T00:00:00Z',
      reason: null,
    })
    const data =
      queryClient.getQueryData<
        Array<{ id: string; last_test_status: string | null; last_tested_at: string | null }>
      >(key)
    expect(data?.[0]?.last_test_status).toBe('success')
    expect(data?.[0]?.last_tested_at).toBe('2026-03-01T00:00:00Z')
  })
})

describe('batchConnectivityIncludesVideoGeneration', () => {
  it('detects video models in testable subset', () => {
    expect(
      batchConnectivityIncludesVideoGeneration([
        { id: '1', capability: 'chat', last_test_status: null },
        { id: '2', capability: 'video_generation', last_test_status: null },
      ])
    ).toBe(true)
    expect(
      batchConnectivityIncludesVideoGeneration([
        { id: '1', capability: 'chat', last_test_status: null },
      ])
    ).toBe(false)
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
      1,
      20,
      '',
      'all',
      '',
    ])
    expect(playgroundTeamModelsQueryKey('team-1', 'cred-1')).toEqual([
      'gateway',
      'models',
      'team-1',
      'callable',
      '',
      'cred-1',
      1,
      20,
      '',
      'all',
      '',
    ])
  })
})

describe('resolveGatewayModelTeamId', () => {
  it('prefers tenant_id over team_id', () => {
    expect(
      resolveGatewayModelTeamId(model({ tenant_id: 'a', team_id: 'b', last_test_status: null }))
    ).toBe('a')
  })

  it('falls back to team_id', () => {
    expect(
      resolveGatewayModelTeamId(model({ tenant_id: null, team_id: 'b', last_test_status: null }))
    ).toBe('b')
  })

  it('returns null when both missing', () => {
    expect(
      resolveGatewayModelTeamId(model({ tenant_id: null, team_id: null, last_test_status: null }))
    ).toBeNull()
  })
})

describe('groupModelsByTeamId', () => {
  it('groups models by tenant', () => {
    const grouped = groupModelsByTeamId([
      model({ id: '1', tenant_id: 'team-a', last_test_status: null }),
      model({ id: '2', tenant_id: 'team-b', last_test_status: null }),
      model({ id: '3', tenant_id: 'team-a', last_test_status: null }),
    ])
    expect(grouped.get('team-a')?.map((m) => m.id)).toEqual(['1', '3'])
    expect(grouped.get('team-b')?.map((m) => m.id)).toEqual(['2'])
  })
})

describe('runChunkedBatchDeleteByTeam', () => {
  it('calls delete per team with chunked ids', async () => {
    const calls: Array<{ teamId: string; chunk: string[] }> = []
    const result = await runChunkedBatchDeleteByTeam(
      [
        model({ id: '1', tenant_id: 'team-a', last_test_status: null }),
        model({ id: '2', tenant_id: 'team-b', last_test_status: null }),
      ],
      (teamId, chunk) => {
        calls.push({ teamId, chunk })
        return Promise.resolve({
          succeeded: chunk,
          failed: [],
          grants_removed: 0,
          budgets_removed: 0,
        })
      }
    )
    expect(calls).toEqual([
      { teamId: 'team-a', chunk: ['1'] },
      { teamId: 'team-b', chunk: ['2'] },
    ])
    expect(result.succeeded).toEqual(['1', '2'])
  })
})

describe('runChunkedBatchResyncByTeam', () => {
  it('calls resync per team', async () => {
    const calls: string[] = []
    await runChunkedBatchResyncByTeam(
      [model({ id: '1', tenant_id: 'team-a', last_test_status: null })],
      (teamId, chunk) => {
        calls.push(`${teamId}:${chunk.join(',')}`)
        return Promise.resolve({ succeeded: chunk, failed: [] })
      }
    )
    expect(calls).toEqual(['team-a:1'])
  })
})

describe('createManagedTeamsTestById', () => {
  it('routes test to correct team', async () => {
    const testModel = (teamId: string, id: string): Promise<GatewayModelTestResult> =>
      Promise.resolve({
        success: true,
        message: `${teamId}/${id}`,
        model: id,
        status: 'success' as const,
        tested_at: '',
        reason: null,
      })
    const testById = createManagedTeamsTestById(
      [model({ id: 'm1', tenant_id: 'team-x', last_test_status: null })],
      testModel
    )
    const result = await testById('m1')
    expect(result.message).toBe('team-x/m1')
  })
})

describe('filterManageableTestableModels', () => {
  it('filters by testable capability and canManage', () => {
    const items = filterManageableTestableModels(
      [
        model({ id: '1', capability: 'chat', last_test_status: null }),
        model({ id: '2', capability: 'moderation', last_test_status: null }),
      ],
      (m) => m.id === '1'
    )
    expect(items.map((m) => m.id)).toEqual(['1'])
  })
})

describe('resolveGatewayModelTeamId', () => {
  it('prefers tenant_id over team_id', () => {
    expect(
      resolveGatewayModelTeamId(model({ tenant_id: 'a', team_id: 'b', last_test_status: null }))
    ).toBe('a')
  })

  it('falls back to team_id', () => {
    expect(
      resolveGatewayModelTeamId(model({ tenant_id: null, team_id: 'b', last_test_status: null }))
    ).toBe('b')
  })

  it('returns null when both missing', () => {
    expect(
      resolveGatewayModelTeamId(model({ tenant_id: null, team_id: null, last_test_status: null }))
    ).toBeNull()
  })
})

describe('groupModelsByTeamId', () => {
  it('groups models by tenant', () => {
    const grouped = groupModelsByTeamId([
      model({ id: '1', tenant_id: 'team-a', last_test_status: null }),
      model({ id: '2', tenant_id: 'team-b', last_test_status: null }),
      model({ id: '3', tenant_id: 'team-a', last_test_status: null }),
    ])
    expect(grouped.get('team-a')?.map((m) => m.id)).toEqual(['1', '3'])
    expect(grouped.get('team-b')?.map((m) => m.id)).toEqual(['2'])
  })
})

describe('runChunkedBatchDeleteByTeam', () => {
  it('calls delete per team with chunked ids', async () => {
    const calls: Array<{ teamId: string; chunk: string[] }> = []
    const result = await runChunkedBatchDeleteByTeam(
      [
        model({ id: '1', tenant_id: 'team-a', last_test_status: null }),
        model({ id: '2', tenant_id: 'team-b', last_test_status: null }),
      ],
      (teamId, chunk) => {
        calls.push({ teamId, chunk })
        return Promise.resolve({
          succeeded: chunk,
          failed: [],
          grants_removed: 0,
          budgets_removed: 0,
        })
      }
    )
    expect(calls).toEqual([
      { teamId: 'team-a', chunk: ['1'] },
      { teamId: 'team-b', chunk: ['2'] },
    ])
    expect(result.succeeded).toEqual(['1', '2'])
  })
})

describe('runChunkedBatchResyncByTeam', () => {
  it('calls resync per team', async () => {
    const calls: string[] = []
    await runChunkedBatchResyncByTeam(
      [model({ id: '1', tenant_id: 'team-a', last_test_status: null })],
      (teamId, chunk) => {
        calls.push(`${teamId}:${chunk.join(',')}`)
        return Promise.resolve({ succeeded: chunk, failed: [] })
      }
    )
    expect(calls).toEqual(['team-a:1'])
  })
})

describe('createManagedTeamsTestById', () => {
  it('routes test to correct team', async () => {
    const testModel = (teamId: string, id: string): Promise<GatewayModelTestResult> =>
      Promise.resolve({
        success: true,
        message: `${teamId}/${id}`,
        model: id,
        status: 'success' as const,
        tested_at: '',
        reason: null,
      })
    const testById = createManagedTeamsTestById(
      [model({ id: 'm1', tenant_id: 'team-x', last_test_status: null })],
      testModel
    )
    const result = await testById('m1')
    expect(result.message).toBe('team-x/m1')
  })
})

describe('filterManageableTestableModels', () => {
  it('filters by testable capability and canManage', () => {
    const items = filterManageableTestableModels(
      [
        model({ id: '1', capability: 'chat', last_test_status: null }),
        model({ id: '2', capability: 'moderation', last_test_status: null }),
      ],
      (m) => m.id === '1'
    )
    expect(items.map((m) => m.id)).toEqual(['1'])
  })
})
