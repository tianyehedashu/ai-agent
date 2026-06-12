import type { GatewayModel } from '@/api/gateway/models'
import type { PersonalGatewayModel } from '@/api/gateway/my-models'

import { channelLabel } from '../utils'
import { gatewayModelDisplayName, personalModelDisplayName } from './gateway-model-display-name'

import type { GatewayModelListItem, GatewayModelListScope } from './types'

function buildSubtitle(provider: string, upstreamModelId: string): string {
  return `${channelLabel(provider)} · ${upstreamModelId}`
}

/** PersonalGatewayModel → 统一列表 ViewModel */
export function fromPersonalModel(model: PersonalGatewayModel): GatewayModelListItem {
  return {
    id: model.id,
    scope: 'personal',
    title: model.display_name,
    displayName: personalModelDisplayName(model),
    routeName: model.name,
    subtitle: buildSubtitle(model.provider, model.model_id),
    upstreamModelId: model.model_id,
    provider: model.provider,
    capability: model.capability,
    modelTypes: [...model.model_types],
    selectorCapabilities: model.selector_capabilities,
    enabled: model.is_active,
    lastTestStatus: model.last_test_status,
    lastTestedAt: model.last_tested_at,
    lastTestReason: model.last_test_reason,
    entitlementStatus: model.entitlement_status,
    entitlementResetAt: model.entitlement_reset_at,
    teamId: null,
    credentialId: model.credential_id,
    credentialName: null,
    source: model,
  }
}

/** GatewayModel → 统一列表 ViewModel */
export function fromGatewayModel(
  model: GatewayModel,
  scope: Exclude<GatewayModelListScope, 'personal'> = 'team',
  routeVirtualModel?: string | null
): GatewayModelListItem {
  return {
    id: model.id,
    scope,
    title: model.name,
    displayName: gatewayModelDisplayName(model),
    subtitle: buildSubtitle(model.provider, model.real_model),
    upstreamModelId: model.real_model,
    provider: model.provider,
    capability: model.capability,
    modelTypes: model.model_types ? [...model.model_types] : [],
    selectorCapabilities: model.selector_capabilities,
    enabled: model.enabled,
    lastTestStatus: model.last_test_status,
    lastTestedAt: model.last_tested_at,
    lastTestReason: model.last_test_reason,
    entitlementStatus: model.entitlement_status,
    entitlementResetAt: model.entitlement_reset_at,
    teamId: model.tenant_id ?? model.team_id,
    credentialId: model.credential_id,
    credentialName: model.credential_name?.trim() ?? null,
    registryKind: model.registry_kind,
    routeVirtualModel,
    source: model,
  }
}
