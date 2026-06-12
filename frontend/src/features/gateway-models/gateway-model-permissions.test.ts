import { describe, expect, it } from 'vitest'

import type { GatewayModel } from '@/api/gateway'

import {
  canDeleteGatewayModel,
  canDeletePersonalGatewayModel,
  canManageGatewayModel,
  canManagePersonalGatewayModel,
  canResyncGatewayModelCapabilities,
  isConfigManagedSystemModel,
  isModelBatchSelectable,
  resolveGatewayModelRegistryKind,
} from './gateway-model-permissions'

const ownerId = 'user-owner'
const viewerId = 'user-viewer'

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
  it('allows credential owner to manage team models', () => {
    expect(
      canManageGatewayModel(
        model({ registry_kind: 'team', credential_created_by_user_id: ownerId }),
        ownerId,
        false,
        false
      )
    ).toBe(true)
  })

  it('allows team admin on legacy team models', () => {
    expect(
      canManageGatewayModel(
        model({ registry_kind: 'team', credential_created_by_user_id: null }),
        viewerId,
        true,
        false
      )
    ).toBe(true)
  })

  it('denies non-owner member on owned team models', () => {
    expect(
      canManageGatewayModel(
        model({ registry_kind: 'team', credential_created_by_user_id: ownerId }),
        viewerId,
        false,
        false
      )
    ).toBe(false)
  })

  it('allows team admin to manage others team models', () => {
    expect(
      canManageGatewayModel(
        model({ registry_kind: 'team', credential_created_by_user_id: ownerId }),
        viewerId,
        true,
        false
      )
    ).toBe(true)
  })

  it('allows model creator to manage their own team models', () => {
    expect(
      canManageGatewayModel(
        model({
          registry_kind: 'team',
          credential_created_by_user_id: ownerId,
          created_by_user_id: viewerId,
        }),
        viewerId,
        false,
        false
      )
    ).toBe(true)
  })

  it('allows platform admin to manage system models', () => {
    expect(canManageGatewayModel(model({ registry_kind: 'system' }), viewerId, false, true)).toBe(
      true
    )
  })

  it('blocks non-admin from managing system models', () => {
    expect(canManageGatewayModel(model({ registry_kind: 'system' }), viewerId, false, false)).toBe(
      false
    )
  })
})

describe('canDeleteGatewayModel', () => {
  it('allows credential owner to delete team models', () => {
    expect(
      canDeleteGatewayModel(
        model({ registry_kind: 'team', credential_created_by_user_id: ownerId }),
        ownerId,
        false,
        false
      )
    ).toBe(true)
  })

  it('allows team admin to delete others team models', () => {
    expect(
      canDeleteGatewayModel(
        model({ registry_kind: 'team', credential_created_by_user_id: ownerId }),
        viewerId,
        true,
        false
      )
    ).toBe(true)
  })

  it('denies non-owner member delete on owned team models', () => {
    expect(
      canDeleteGatewayModel(
        model({ registry_kind: 'team', credential_created_by_user_id: ownerId }),
        viewerId,
        false,
        false
      )
    ).toBe(false)
  })

  it('allows model creator to delete their own team models', () => {
    expect(
      canDeleteGatewayModel(
        model({
          registry_kind: 'team',
          credential_created_by_user_id: ownerId,
          created_by_user_id: viewerId,
        }),
        viewerId,
        false,
        false
      )
    ).toBe(true)
  })

  it('allows platform admin to delete non-managed system models', () => {
    expect(canDeleteGatewayModel(model({ registry_kind: 'system' }), viewerId, false, true)).toBe(
      true
    )
  })

  it('blocks platform admin from deleting config-managed system models', () => {
    expect(
      canDeleteGatewayModel(
        model({ registry_kind: 'system', tags: { managed_by: 'config' } }),
        viewerId,
        false,
        true
      )
    ).toBe(false)
  })
})

describe('canResyncGatewayModelCapabilities', () => {
  it('matches canManageGatewayModel', () => {
    const owned = model({ registry_kind: 'team', credential_created_by_user_id: ownerId })
    const systemModel = model({ registry_kind: 'system' })
    const managed = model({ registry_kind: 'system', tags: { managed_by: 'config' } })
    expect(canResyncGatewayModelCapabilities(owned, ownerId, false, false)).toBe(true)
    expect(canResyncGatewayModelCapabilities(systemModel, viewerId, false, true)).toBe(true)
    expect(canResyncGatewayModelCapabilities(managed, viewerId, false, true)).toBe(true)
    expect(canManageGatewayModel(managed, viewerId, false, true)).toBe(true)
    expect(canDeleteGatewayModel(managed, viewerId, false, true)).toBe(false)
  })
})

describe('isModelBatchSelectable', () => {
  it('matches canDeleteGatewayModel for system tab', () => {
    const ctx = { preferSystem: true } as const
    const deletable = model({ registry_kind: 'system' })
    const managed = model({ registry_kind: 'system', tags: { managed_by: 'config' } })
    expect(isModelBatchSelectable(deletable, viewerId, false, true, ctx)).toBe(true)
    expect(isModelBatchSelectable(managed, viewerId, false, true, ctx)).toBe(false)
    expect(isModelBatchSelectable(deletable, viewerId, false, false, ctx)).toBe(false)
  })

  it('allows team admin to select team models', () => {
    const teamModel = model({ registry_kind: 'team', credential_created_by_user_id: ownerId })
    expect(isModelBatchSelectable(teamModel, viewerId, true, false)).toBe(true)
    expect(isModelBatchSelectable(teamModel, viewerId, false, false)).toBe(false)
  })
})

describe('isConfigManagedSystemModel', () => {
  it('detects config-managed system models', () => {
    expect(
      isConfigManagedSystemModel(model({ registry_kind: 'system', tags: { managed_by: 'config' } }))
    ).toBe(true)
  })
})

describe('canManagePersonalGatewayModel', () => {
  it('allows owner with auth session', () => {
    expect(canManagePersonalGatewayModel('user-1', 'user-1', true)).toBe(true)
    expect(canDeletePersonalGatewayModel('user-1', 'user-1', true)).toBe(true)
  })

  it('denies other viewers and anonymous', () => {
    expect(canManagePersonalGatewayModel('user-1', 'user-2', true)).toBe(false)
    expect(canManagePersonalGatewayModel('user-1', 'user-2', true)).toBe(false)
    expect(canManagePersonalGatewayModel('user-1', null, false)).toBe(false)
  })
})
