import { describe, expect, it } from 'vitest'

import type { GatewayModel } from '@/api/gateway/models'
import type { GatewayRoute } from '@/api/gateway/routes'

import {
  buildBudgetModelOptions,
  buildUpstreamQuotaModelOptions,
  groupBudgetModelOptions,
} from './budget-model-options'

function model(partial: Partial<GatewayModel> & Pick<GatewayModel, 'name'>): GatewayModel {
  return {
    id: 'm1',
    team_id: null,
    capability: 'chat',
    real_model: partial.name,
    credential_id: 'c1',
    provider: 'openai',
    weight: 1,
    rpm_limit: null,
    tpm_limit: null,
    enabled: true,
    last_test_status: null,
    last_tested_at: null,
    last_test_reason: null,
    created_at: '2026-01-01T00:00:00Z',
    ...partial,
  }
}

function route(partial: Partial<GatewayRoute> & Pick<GatewayRoute, 'virtual_model'>): GatewayRoute {
  return {
    id: 'r1',
    team_id: null,
    primary_models: ['gpt-4'],
    fallbacks_general: [],
    fallbacks_content_policy: [],
    fallbacks_context_window: [],
    strategy: 'weighted',
    enabled: true,
    ...partial,
  }
}

describe('buildBudgetModelOptions', () => {
  it('returns empty list for empty input', () => {
    expect(buildBudgetModelOptions({ models: [], routes: [], existingModelNames: [] })).toEqual([])
  })

  it('deduplicates registry models by name', () => {
    const options = buildBudgetModelOptions({
      models: [model({ name: 'gpt-4' }), model({ id: 'm2', name: 'gpt-4' })],
      routes: [],
      existingModelNames: [],
    })
    expect(options).toHaveLength(1)
    expect(options[0]?.group).toBe('registry')
  })

  it('skips routes whose virtual_model already exists in registry', () => {
    const options = buildBudgetModelOptions({
      models: [model({ name: 'smart-route' })],
      routes: [route({ virtual_model: 'smart-route' })],
      existingModelNames: [],
    })
    expect(options).toHaveLength(1)
    expect(options[0]?.group).toBe('registry')
  })

  it('includes virtual routes not in registry', () => {
    const options = buildBudgetModelOptions({
      models: [model({ name: 'gpt-4' })],
      routes: [route({ virtual_model: 'my-virtual' })],
      existingModelNames: [],
    })
    expect(options.map((o) => o.name)).toEqual(['gpt-4', 'my-virtual'])
    expect(options[1]?.group).toBe('route')
  })

  it('preserves legacy model names from existing budgets', () => {
    const options = buildBudgetModelOptions({
      models: [model({ name: 'gpt-4' })],
      routes: [],
      existingModelNames: ['retired-model', null, '', 'gpt-4'],
    })
    expect(options.map((o) => o.name)).toEqual(['gpt-4', 'retired-model'])
    expect(options[1]?.group).toBe('legacy')
  })

  it('deduplicates virtual routes by virtual_model', () => {
    const options = buildBudgetModelOptions({
      models: [],
      routes: [
        route({ virtual_model: 'my-route' }),
        route({ id: 'r2', virtual_model: 'my-route' }),
      ],
      existingModelNames: [],
    })
    expect(options).toHaveLength(1)
    expect(options[0]?.group).toBe('route')
  })

  it('sorts by group then name', () => {
    const options = buildBudgetModelOptions({
      models: [model({ name: 'z-model' }), model({ name: 'a-model' })],
      routes: [route({ virtual_model: 'route-b' })],
      existingModelNames: ['legacy-x'],
    })
    expect(options.map((o) => `${o.group}:${o.name}`)).toEqual([
      'registry:a-model',
      'registry:z-model',
      'route:route-b',
      'legacy:legacy-x',
    ])
  })
})

describe('groupBudgetModelOptions', () => {
  it('groups options by kind', () => {
    const options = buildBudgetModelOptions({
      models: [model({ name: 'gpt-4' })],
      routes: [route({ virtual_model: 'route-a' })],
      existingModelNames: ['legacy-x'],
    })
    const grouped = groupBudgetModelOptions(options)
    expect(grouped.registry.map((o) => o.name)).toEqual(['gpt-4'])
    expect(grouped.route.map((o) => o.name)).toEqual(['route-a'])
    expect(grouped.legacy.map((o) => o.name)).toEqual(['legacy-x'])
  })
})

describe('buildUpstreamQuotaModelOptions', () => {
  it('filters by credential and uses real_model as option name', () => {
    const options = buildUpstreamQuotaModelOptions({
      models: [
        model({ name: 'alias-a', real_model: 'gpt-4o', credential_id: 'c1' }),
        model({ name: 'alias-b', real_model: 'gpt-4o-mini', credential_id: 'c2' }),
        model({ name: 'alias-c', real_model: 'claude-3', credential_id: 'c1' }),
      ],
      credentialIds: ['c1'],
      existingModelNames: [],
    })
    expect(options.map((o) => o.name).sort()).toEqual(['claude-3', 'gpt-4o'])
  })

  it('filters legacy names to selected credentials only', () => {
    const options = buildUpstreamQuotaModelOptions({
      models: [model({ name: 'alias-a', real_model: 'gpt-4o', credential_id: 'c1' })],
      credentialIds: ['c1'],
      existingModelNames: ['gpt-4o', 'orphan-model'],
    })
    expect(options.map((o) => o.name)).toEqual(['gpt-4o'])
  })
})
