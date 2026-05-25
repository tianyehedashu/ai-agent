import { describe, expect, it } from 'vitest'

import type { GatewayModel } from '@/api/gateway'

import {
  canDeleteGatewayModel,
  canManageGatewayModel,
  canResyncGatewayModelCapabilities,
  isConfigManagedSystemModel,
  isModelBatchSelectable,
  resolveGatewayModelRegistryKind,
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

describe('resolveGatewayModelRegistryKind', () => {
  it('prefers explicit registry_kind', () => {
    expect(resolveGatewayModelRegistryKind(model({ registry_kind: 'system' }))).toBe('system')
  })

  it('uses preferSystem when registry_kind missing', () => {
    expect(
      resolveGatewayModelRegistryKind(model({ registry_kind: undefined }), { preferSystem: true })
    ).toBe('system')
  })

  it('infers system from visibility', () => {
    expect(
      resolveGatewayModelRegistryKind(
        model({ team_id: null, tenant_id: null, visibility: 'public' })
      )
    ).toBe('system')
  })
})

describe('canManageGatewayModel', () => {
  it('allows team admin to manage team models', () => {
    expect(canManageGatewayModel(model({ registry_kind: 'team' }), true, false)).toBe(true)
  })

  it('allows platform admin to manage system models', () => {
    expect(canManageGatewayModel(model({ registry_kind: 'system' }), false, true)).toBe(true)
  })

  it('allows platform admin on system tab when registry_kind missing', () => {
    expect(
      canManageGatewayModel(model({ registry_kind: undefined }), false, true, {
        preferSystem: true,
      })
    ).toBe(true)
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

  it('allows platform admin to delete on system tab without registry_kind', () => {
    expect(
      canDeleteGatewayModel(model({ registry_kind: undefined }), false, true, {
        preferSystem: true,
      })
    ).toBe(true)
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

describe('canResyncGatewayModelCapabilities', () => {
  it('matches canDeleteGatewayModel', () => {
    const teamModel = model({ registry_kind: 'team' })
    const systemModel = model({ registry_kind: 'system' })
    const managed = model({ registry_kind: 'system', tags: { managed_by: 'config' } })
    expect(canResyncGatewayModelCapabilities(teamModel, true, false)).toBe(true)
    expect(canResyncGatewayModelCapabilities(systemModel, false, true)).toBe(true)
    expect(canResyncGatewayModelCapabilities(managed, false, true)).toBe(false)
  })
})

describe('isModelBatchSelectable', () => {
  it('matches canDeleteGatewayModel for system tab', () => {
    const ctx = { preferSystem: true } as const
    const deletable = model({ registry_kind: 'system' })
    const managed = model({ registry_kind: 'system', tags: { managed_by: 'config' } })
    expect(isModelBatchSelectable(deletable, false, true, ctx)).toBe(true)
    expect(isModelBatchSelectable(managed, false, true, ctx)).toBe(false)
    expect(isModelBatchSelectable(deletable, false, false, ctx)).toBe(false)
  })

  it('allows team admin to select team models', () => {
    const teamModel = model({ registry_kind: 'team' })
    expect(isModelBatchSelectable(teamModel, true, false)).toBe(true)
    expect(isModelBatchSelectable(teamModel, false, false)).toBe(false)
  })
})

describe('isConfigManagedSystemModel', () => {
  it('detects config-managed system models', () => {
    expect(
      isConfigManagedSystemModel(model({ registry_kind: 'system', tags: { managed_by: 'config' } }))
    ).toBe(true)
  })
})
