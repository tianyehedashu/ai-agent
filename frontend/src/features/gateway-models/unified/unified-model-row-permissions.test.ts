import { describe, expect, it } from 'vitest'

import type { GatewayModel } from '@/api/gateway/models'
import type { PersonalGatewayModel } from '@/api/gateway/my-models'
import type { GatewayTeam } from '@/api/gateway/teams'
import { fromGatewayModel, fromPersonalModel } from '@/features/gateway-models/list/adapters'
import {
  canBatchSelectUnifiedModelItem,
  canDeleteUnifiedModelItem,
  canManageUnifiedModelItem,
  canResyncUnifiedModelItem,
  isConfigManagedUnifiedModelItem,
  type UnifiedModelRowPermissionContext,
} from '@/features/gateway-models/unified/unified-model-row-permissions'

const ownerId = 'user-owner'
const viewerId = 'user-viewer'

function team(id: string, teamRole: string | null = 'admin'): GatewayTeam {
  return {
    id,
    name: `Team ${id}`,
    slug: id,
    kind: 'shared',
    owner_user_id: ownerId,
    team_role: teamRole,
  }
}

function ctx(
  partial: Partial<UnifiedModelRowPermissionContext> = {}
): UnifiedModelRowPermissionContext {
  const teamById = new Map<string, GatewayTeam>([['t1', team('t1')]])
  return {
    viewerUserId: ownerId,
    isPlatformAdmin: false,
    hasAuthSession: true,
    teamById,
    ...partial,
  }
}

function personalModel(
  partial: Partial<PersonalGatewayModel> & Pick<PersonalGatewayModel, 'id'>
): PersonalGatewayModel {
  return {
    user_id: ownerId,
    display_name: 'My Model',
    provider: 'openai',
    model_id: 'gpt-4o',
    api_key_masked: 'sk-***',
    has_api_key: true,
    api_base: null,
    credential_id: 'cred-1',
    model_types: ['text'],
    config: null,
    is_active: true,
    is_system: false,
    capability: 'chat',
    name: 'personal/openai/gpt-4o',
    last_test_status: null,
    last_tested_at: null,
    last_test_reason: null,
    created_at: '2026-01-01T00:00:00.000Z',
    updated_at: null,
    ...partial,
  }
}

function gatewayModel(partial: Partial<GatewayModel> & Pick<GatewayModel, 'id'>): GatewayModel {
  return {
    tenant_id: 't1',
    team_id: 't1',
    name: 'alias/gpt',
    capability: 'chat',
    real_model: 'gpt-4o-mini',
    credential_id: 'cred-2',
    provider: 'openai',
    weight: 1,
    rpm_limit: null,
    tpm_limit: null,
    enabled: true,
    last_test_status: null,
    last_tested_at: null,
    last_test_reason: null,
    created_at: '2026-01-01T00:00:00.000Z',
    ...partial,
  }
}

describe('unified-model-row-permissions', () => {
  it('allows personal model management for authenticated users', () => {
    const item = fromPersonalModel(personalModel({ id: 'pm-1' }))
    expect(canManageUnifiedModelItem(item, ctx())).toBe(true)
    expect(canDeleteUnifiedModelItem(item, ctx())).toBe(true)
    expect(canBatchSelectUnifiedModelItem(item, ctx())).toBe(true)
  })

  it('denies all actions without auth session', () => {
    const item = fromPersonalModel(personalModel({ id: 'pm-1' }))
    const noAuth = ctx({ hasAuthSession: false, viewerUserId: null })
    expect(canManageUnifiedModelItem(item, noAuth)).toBe(false)
    expect(canBatchSelectUnifiedModelItem(item, noAuth)).toBe(false)
  })

  it('respects team write policy for team models', () => {
    const item = fromGatewayModel(
      gatewayModel({
        id: 'gm-1',
        registry_kind: 'team',
        credential_created_by_user_id: ownerId,
      }),
      'team'
    )
    const readOnlyTeam = ctx({
      teamById: new Map([['t1', team('t1', 'member')]]),
      viewerUserId: viewerId,
    })
    expect(canManageUnifiedModelItem(item, readOnlyTeam)).toBe(false)
    expect(canBatchSelectUnifiedModelItem(item, readOnlyTeam)).toBe(false)
  })

  it('allows team admin to manage and delete member-owned team models', () => {
    const item = fromGatewayModel(
      gatewayModel({
        id: 'gm-admin',
        registry_kind: 'team',
        credential_created_by_user_id: ownerId,
      }),
      'team'
    )
    const adminCtx = ctx({
      teamById: new Map([['t1', team('t1', 'admin')]]),
      viewerUserId: viewerId,
    })
    expect(canManageUnifiedModelItem(item, adminCtx)).toBe(true)
    expect(canDeleteUnifiedModelItem(item, adminCtx)).toBe(true)
    expect(canBatchSelectUnifiedModelItem(item, adminCtx)).toBe(true)
  })

  it('allows credential owner to manage team model without admin role', () => {
    const item = fromGatewayModel(
      gatewayModel({
        id: 'gm-2',
        registry_kind: 'team',
        credential_created_by_user_id: ownerId,
      }),
      'team'
    )
    const memberCtx = ctx({
      teamById: new Map([['t1', team('t1', 'member')]]),
      viewerUserId: ownerId,
    })
    expect(canManageUnifiedModelItem(item, memberCtx)).toBe(true)
    expect(canBatchSelectUnifiedModelItem(item, memberCtx)).toBe(true)
  })

  it('blocks batch select for config-managed system models', () => {
    const item = fromGatewayModel(
      gatewayModel({
        id: 'gm-sys',
        registry_kind: 'system',
        tags: { managed_by: 'config' },
      }),
      'system'
    )
    expect(isConfigManagedUnifiedModelItem(item)).toBe(true)
    expect(canBatchSelectUnifiedModelItem(item, ctx({ isPlatformAdmin: true }))).toBe(false)
  })

  it('allows platform admin to resync system models', () => {
    const item = fromGatewayModel(
      gatewayModel({ id: 'gm-sys-2', registry_kind: 'system' }),
      'system'
    )
    expect(canResyncUnifiedModelItem(item, ctx({ isPlatformAdmin: true }))).toBe(true)
  })
})
