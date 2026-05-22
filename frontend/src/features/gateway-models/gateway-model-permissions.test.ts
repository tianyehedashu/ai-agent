import { describe, expect, it } from 'vitest'

import type { GatewayModel } from '@/api/gateway'

import {
  canDeleteGatewayModel,
  canManageGatewayModel,
  isConfigManagedSystemModel,
} from './gateway-model-permissions'

function model(partial: Partial<GatewayModel>): GatewayModel {
  return {
    id: '1',
    team_id: 't',
    name: 'test/model',
    capability: 'chat',
    real_model: 'gpt-4o',
    credential_id: 'c',
    provider: 'openai',
    weight: 1,
    rpm_limit: null,
    tpm_limit: null,
    enabled: true,
    last_test_status: null,
    last_tested_at: null,
    last_test_reason: null,
    created_at: '2024-01-01T00:00:00Z',
    ...partial,
  }
}

describe('canManageGatewayModel', () => {
  it('allows team admin to manage team models', () => {
    expect(canManageGatewayModel(model({ registry_kind: 'team' }), true, false)).toBe(true)
  })

  it('allows platform admin to manage system models', () => {
    expect(canManageGatewayModel(model({ registry_kind: 'system' }), false, true)).toBe(true)
  })

  it('blocks non-admin from managing system models', () => {
    expect(canManageGatewayModel(model({ registry_kind: 'system' }), false, false)).toBe(false)
  })
})

describe('canDeleteGatewayModel', () => {
  it('allows team admin to delete team models', () => {
    expect(canDeleteGatewayModel(model({ registry_kind: 'team' }), true, false)).toBe(true)
  })

  it('allows platform admin to delete non-managed system models', () => {
    expect(canDeleteGatewayModel(model({ registry_kind: 'system' }), false, true)).toBe(true)
  })

  it('blocks platform admin from deleting config-managed system models', () => {
    expect(
      canDeleteGatewayModel(
        model({ registry_kind: 'system', tags: { managed_by: 'config' } }),
        false,
        true
      )
    ).toBe(false)
  })
})

describe('isConfigManagedSystemModel', () => {
  it('detects config-managed system models', () => {
    expect(
      isConfigManagedSystemModel(model({ registry_kind: 'system', tags: { managed_by: 'config' } }))
    ).toBe(true)
  })
})
