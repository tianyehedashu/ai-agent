/**
 * API Key Gateway 授权编辑器纯函数（独立文件以满足 react-refresh/only-export-components）
 */

import type { ApiKeyGatewayGrantRequest } from '@/types/api-key'

import type { GrantDraft } from './api-key-grant-editor'

function toDraft(grant: ApiKeyGatewayGrantRequest, localId: string): GrantDraft {
  return {
    localId,
    team_id: grant.team_id,
    allowed_models: grant.allowed_models ?? [],
    allowed_capabilities: grant.allowed_capabilities ?? [],
    rpm_limit: grant.rpm_limit ?? null,
    tpm_limit: grant.tpm_limit ?? null,
    store_full_messages: grant.store_full_messages ?? false,
    guardrail_enabled: grant.guardrail_enabled ?? false,
  }
}

function draftToRequest(draft: GrantDraft): ApiKeyGatewayGrantRequest {
  return {
    team_id: draft.team_id,
    allowed_models: draft.allowed_models,
    allowed_capabilities: draft.allowed_capabilities,
    rpm_limit: draft.rpm_limit,
    tpm_limit: draft.tpm_limit,
    store_full_messages: draft.store_full_messages,
    guardrail_enabled: draft.guardrail_enabled,
  }
}

export function grantsToRequests(grants: GrantDraft[]): ApiKeyGatewayGrantRequest[] {
  return grants.map(draftToRequest)
}

export function gatewayGrantsToDrafts(
  grants: Array<{
    team_id: string
    allowed_models: string[]
    allowed_capabilities: string[]
    rpm_limit: number | null
    tpm_limit: number | null
    store_full_messages: boolean
    guardrail_enabled: boolean
  }>
): GrantDraft[] {
  return grants.map((g) =>
    toDraft(
      {
        team_id: g.team_id,
        allowed_models: g.allowed_models,
        allowed_capabilities: g.allowed_capabilities,
        rpm_limit: g.rpm_limit,
        tpm_limit: g.tpm_limit,
        store_full_messages: g.store_full_messages,
        guardrail_enabled: g.guardrail_enabled,
      },
      crypto.randomUUID()
    )
  )
}
