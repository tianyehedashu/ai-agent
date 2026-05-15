import { describe, expect, it } from 'vitest'

import type { GatewayModel, GatewayRoute } from '@/api/gateway'

import {
  classifyFailureReason,
  formatUsageLine,
  matchesHealthFilter,
  pickInspectorModelId,
  routesReferencingModel,
  runWithConcurrency,
  summarizeHealth,
} from './utils'

import type { HealthFilter } from './constants'

function model(
  partial: Partial<GatewayModel> & Pick<GatewayModel, 'last_test_status'>
): GatewayModel {
  return {
    id: '1',
    team_id: 't',
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
