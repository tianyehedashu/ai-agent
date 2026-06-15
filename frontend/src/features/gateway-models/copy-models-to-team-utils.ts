/**
 * 模型批量导入到团队 — 纯函数（分组、目标团队、请求体构建）。
 */

import type { ProviderCredential } from '@/api/gateway'
import type {
  CopyModelsToTeamBody,
  ModelCopyCredentialMode,
  ModelCopyCredentialPlanBody,
} from '@/api/gateway/models'
import type { GatewayTeam } from '@/api/gateway/teams'
import { canBindCredentialForTeamModel } from '@/features/gateway-credentials/credential-permissions'
import type { GatewayModelListItem } from '@/features/gateway-models/list/types'

export interface ModelCopyCredentialGroup {
  sourceCredentialId: string
  provider: string
  credentialName: string
  modelIds: string[]
  sourceTeamIds: string[]
}

export interface ModelCopyGroupPlanState {
  mode: ModelCopyCredentialMode
  destinationCredentialId: string | null
}

export function groupSelectedModelsForCopy(
  items: readonly GatewayModelListItem[]
): ModelCopyCredentialGroup[] {
  const byCred = new Map<string, ModelCopyCredentialGroup>()
  for (const item of items) {
    const credId = item.credentialId
    if (!credId) continue
    const existing = byCred.get(credId)
    const teamId = item.teamId ?? null
    if (existing) {
      existing.modelIds.push(item.id)
      if (teamId && !existing.sourceTeamIds.includes(teamId)) {
        existing.sourceTeamIds.push(teamId)
      }
      continue
    }
    byCred.set(credId, {
      sourceCredentialId: credId,
      provider: item.provider,
      credentialName: item.credentialName ?? credId.slice(0, 8),
      modelIds: [item.id],
      sourceTeamIds: teamId ? [teamId] : [],
    })
  }
  return [...byCred.values()]
}

export function buildDestinationTeamOptions(
  contributorTeams: readonly GatewayTeam[],
  sourceTeamIds: readonly string[],
  personalTeamId: string | null | undefined
): GatewayTeam[] {
  const blocked = new Set(sourceTeamIds)
  if (personalTeamId) blocked.add(personalTeamId)
  return contributorTeams.filter((team) => !blocked.has(team.id))
}

export function filterDestinationCredentialsForGroup(
  teamCredentials: readonly ProviderCredential[],
  group: ModelCopyCredentialGroup,
  destinationTeamId: string,
  viewerUserId: string | null | undefined,
  canWriteDestTeam: boolean
): ProviderCredential[] {
  return teamCredentials.filter(
    (cred) =>
      cred.tenant_id === destinationTeamId &&
      cred.management_access !== 'metadata' &&
      cred.provider === group.provider &&
      canBindCredentialForTeamModel(cred, viewerUserId, canWriteDestTeam)
  )
}

export function buildDefaultGroupPlans(
  groups: readonly ModelCopyCredentialGroup[],
  destinationTeamId: string,
  teamCredentials: readonly ProviderCredential[],
  viewerUserId: string | null | undefined,
  canWriteDestTeam: boolean
): Record<string, ModelCopyGroupPlanState> {
  const plans: Record<string, ModelCopyGroupPlanState> = {}
  for (const group of groups) {
    const matches = filterDestinationCredentialsForGroup(
      teamCredentials,
      group,
      destinationTeamId,
      viewerUserId,
      canWriteDestTeam
    )
    plans[group.sourceCredentialId] = {
      mode: matches.length > 0 ? 'existing' : 'copy_credential',
      destinationCredentialId: matches[0]?.id ?? null,
    }
  }
  return plans
}

export function buildCopyModelsToTeamBody(
  selectedItems: readonly GatewayModelListItem[],
  destinationTeamId: string,
  groupPlans: Record<string, ModelCopyGroupPlanState>
): CopyModelsToTeamBody {
  const groups = groupSelectedModelsForCopy(selectedItems)
  const credential_plans: ModelCopyCredentialPlanBody[] = groups.map((group) => {
    const plan = groupPlans[group.sourceCredentialId]
    if (plan.mode === 'existing') {
      return {
        source_credential_id: group.sourceCredentialId,
        mode: 'existing',
        destination_credential_id: plan.destinationCredentialId ?? undefined,
      }
    }
    return {
      source_credential_id: group.sourceCredentialId,
      mode: 'copy_credential',
    }
  })
  return {
    model_ids: selectedItems.map((item) => item.id),
    destination_team_id: destinationTeamId,
    credential_plans,
  }
}

export function isCopyModelsPlanValid(
  groups: readonly ModelCopyCredentialGroup[],
  groupPlans: Record<string, ModelCopyGroupPlanState>
): boolean {
  if (groups.length === 0) return false
  return groups.every((group) => {
    const plan = groupPlans[group.sourceCredentialId]
    if (plan.mode === 'existing') {
      return plan.destinationCredentialId !== null && plan.destinationCredentialId !== ''
    }
    return true
  })
}
