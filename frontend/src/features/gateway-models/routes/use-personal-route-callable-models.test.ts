/**
 * @see use-personal-route-callable-models.ts
 */

import { describe, expect, it } from 'vitest'

import type { RouteCallableModel } from '@/api/gateway'

import { routeCallableToPickerModel } from './use-personal-route-callable-models'

function callableModel(
  partial: Partial<RouteCallableModel> & Pick<RouteCallableModel, 'name' | 'route_ref'>
): RouteCallableModel {
  const { name, route_ref, ...rest } = partial
  return {
    id: rest.id ?? name,
    tenant_id: rest.tenant_id ?? 'team-1',
    team_id: rest.team_id ?? 'team-1',
    name,
    route_ref,
    team_kind: rest.team_kind ?? 'shared',
    team_slug: rest.team_slug ?? 'collab',
    prefix_dispatchable: rest.prefix_dispatchable ?? true,
    capability: 'chat',
    real_model: name,
    credential_id: 'cred-1',
    provider: 'openai',
    weight: 1,
    rpm_limit: null,
    tpm_limit: null,
    enabled: true,
    last_test_status: 'success',
    last_tested_at: null,
    last_test_reason: null,
    created_at: '',
    ...rest,
  }
}

describe('routeCallableToPickerModel', () => {
  it('maps route_ref to picker name and keeps registry_name', () => {
    const item = callableModel({
      name: 'gpt-4o',
      route_ref: 'collab-team/gpt-4o',
      team_kind: 'shared',
    })
    const picker = routeCallableToPickerModel(item)
    expect(picker.name).toBe('collab-team/gpt-4o')
    expect(picker.registry_name).toBe('gpt-4o')
    expect(picker.team_kind).toBe('shared')
  })

  it('uses bare name for personal models', () => {
    const item = callableModel({
      name: 'my-model',
      route_ref: 'my-model',
      team_kind: 'personal',
      team_slug: null,
    })
    const picker = routeCallableToPickerModel(item)
    expect(picker.name).toBe('my-model')
    expect(picker.registry_name).toBe('my-model')
  })
})
