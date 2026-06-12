import { describe, expect, it } from 'vitest'

import type { GatewayModel } from '@/api/gateway/models'
import type { PersonalGatewayModel } from '@/api/gateway/my-models'

import { fromGatewayModel, fromPersonalModel } from './adapters'

function personalModel(
  partial: Partial<PersonalGatewayModel> & Pick<PersonalGatewayModel, 'id'>
): PersonalGatewayModel {
  return {
    user_id: 'user-1',
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
    last_test_status: 'success',
    last_tested_at: '2026-05-01T00:00:00.000Z',
    last_test_reason: null,
    created_at: '2026-01-01T00:00:00.000Z',
    updated_at: null,
    ...partial,
  }
}

function gatewayModel(partial: Partial<GatewayModel> & Pick<GatewayModel, 'id'>): GatewayModel {
  return {
    tenant_id: 'team-1',
    team_id: 'team-1',
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

describe('fromPersonalModel', () => {
  it('maps display fields and entitlement', () => {
    const item = fromPersonalModel(
      personalModel({
        id: 'pm-1',
        display_name: 'Display',
        name: 'route/name',
        model_id: 'upstream-id',
        provider: 'anthropic',
        is_active: false,
        entitlement_status: 'exhausted',
        entitlement_reset_at: '2026-06-01T00:00:00.000Z',
      })
    )

    expect(item).toMatchObject({
      id: 'pm-1',
      scope: 'personal',
      title: 'Display',
      displayName: 'Display',
      routeName: 'route/name',
      upstreamModelId: 'upstream-id',
      subtitle: 'Anthropic · upstream-id',
      enabled: false,
      entitlementStatus: 'exhausted',
      entitlementResetAt: '2026-06-01T00:00:00.000Z',
      teamId: null,
    })
    expect(item.source).toMatchObject({ id: 'pm-1' })
  })

  it('copies model types and selector capabilities', () => {
    const item = fromPersonalModel(
      personalModel({
        id: 'pm-2',
        model_types: ['text', 'image'],
        selector_capabilities: { supports_vision: true },
      })
    )

    expect(item.modelTypes).toEqual(['text', 'image'])
    expect(item.selectorCapabilities).toEqual({ supports_vision: true })
  })
})

describe('fromGatewayModel', () => {
  it('maps team registry fields by default', () => {
    const item = fromGatewayModel(
      gatewayModel({
        id: 'gm-1',
        name: 'team/alias',
        real_model: 'deepseek/deepseek-chat',
        provider: 'deepseek',
        enabled: false,
        registry_kind: 'team',
      })
    )

    expect(item).toMatchObject({
      id: 'gm-1',
      scope: 'team',
      title: 'team/alias',
      upstreamModelId: 'deepseek/deepseek-chat',
      subtitle: 'DeepSeek · deepseek/deepseek-chat',
      enabled: false,
      teamId: 'team-1',
      registryKind: 'team',
    })
    expect(item.routeName).toBeUndefined()
    expect(item.displayName).toBe('team/alias')
  })

  it('maps tags.display_name to displayName', () => {
    const item = fromGatewayModel(
      gatewayModel({
        id: 'gm-dn',
        tags: { display_name: '通义 Max' },
      })
    )
    expect(item.displayName).toBe('通义 Max')
  })

  it('falls back displayName to registration name', () => {
    const item = fromGatewayModel(gatewayModel({ id: 'gm-alias', name: 'glm-5.1' }))
    expect(item.displayName).toBe('glm-5.1')
  })

  it('accepts system scope override', () => {
    const item = fromGatewayModel(
      gatewayModel({
        id: 'sys-1',
        tenant_id: null,
        team_id: null,
        registry_kind: 'system',
        visibility: 'public',
        entitlement_status: 'active',
      }),
      'system'
    )

    expect(item.scope).toBe('system')
    expect(item.registryKind).toBe('system')
    expect(item.entitlementStatus).toBe('active')
  })

  it('maps credential_name from gateway model', () => {
    const item = fromGatewayModel(
      gatewayModel({
        id: 'gm-cred',
        credential_name: '  OpenAI 生产  ',
      })
    )
    expect(item.credentialName).toBe('OpenAI 生产')
  })

  it('sets routeVirtualModel when provided', () => {
    const item = fromGatewayModel(
      gatewayModel({
        id: 'gm-route',
        name: 'deepseek-chat--a1b2c3d4',
      }),
      'team',
      'deepseek-chat'
    )

    expect(item.routeVirtualModel).toBe('deepseek-chat')
  })

  it('leaves routeVirtualModel undefined when not provided', () => {
    const item = fromGatewayModel(
      gatewayModel({
        id: 'gm-standalone',
        name: 'standalone-model',
      })
    )

    expect(item.routeVirtualModel).toBeUndefined()
  })
})
