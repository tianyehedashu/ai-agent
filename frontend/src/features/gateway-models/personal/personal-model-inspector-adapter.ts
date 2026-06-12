import type { GatewayModel } from '@/api/gateway/models'
import type { PersonalGatewayModel } from '@/api/gateway/my-models'

/** 个人模型 → ModelInspector 使用的 GatewayModel 视图（只读映射，保存走 personal PATCH）。 */
export function personalModelToInspectorModel(model: PersonalGatewayModel): GatewayModel {
  return {
    id: model.id,
    tenant_id: null,
    team_id: null,
    name: model.name,
    capability: model.capability,
    real_model: model.model_id,
    credential_id: model.credential_id,
    provider: model.provider,
    credential_name: null,
    credential_created_by_user_id: model.user_id,
    created_by_user_id: model.user_id,
    weight: 1,
    rpm_limit: null,
    tpm_limit: null,
    enabled: model.is_active,
    tags: null,
    upstream_call_shape: null,
    model_types: [...model.model_types],
    selector_capabilities: model.selector_capabilities,
    last_test_status: model.last_test_status,
    last_tested_at: model.last_tested_at,
    last_test_reason: model.last_test_reason,
    entitlement_status: model.entitlement_status,
    entitlement_reset_at: model.entitlement_reset_at,
    created_at: model.created_at ?? new Date(0).toISOString(),
  }
}

export interface PersonalModelInspectorContext {
  displayName: string
  userId: string | null
}

export function personalModelInspectorContext(
  model: PersonalGatewayModel
): PersonalModelInspectorContext {
  return {
    displayName: model.display_name,
    userId: model.user_id,
  }
}
