/**
 * Playground 团队模型拉取策略：与团队 Tab 聚合列表对齐。
 *
 * 团队/系统凭据筛选时走 ``/managed-team-models``（成员可读他人注册的模型）；
 * 单团队 ``/teams/{id}/models?credential_id=`` 会校验凭据 reveal 权限，成员对他人凭据 404。
 */

import type { GatewayModel } from '@/api/gateway/models'
import { resolveGatewayModelTeamId } from '@/features/gateway-models/utils'

export function shouldQueryManagedTeamModelsForPlayground(
  teamCredentialFilter: string,
  isPersonalCredential: boolean
): boolean {
  return teamCredentialFilter.length > 0 && !isPersonalCredential
}

export function filterPlaygroundManagedTeamModels(
  items: readonly GatewayModel[],
  contextTeamId: string | null
): GatewayModel[] {
  if (!contextTeamId) return [...items]
  return items.filter((model) => resolveGatewayModelTeamId(model) === contextTeamId)
}
