import {
  gatewayApi,
  type QuotaRuleBatchUpsertResponse,
  type QuotaRuleUpsertBody,
} from '@/api/gateway'
import {
  collectQuotaBatchTargetTeamIds,
  resolveActorCredentialContextTeamId,
} from '@/features/gateway-credentials/hooks/use-actor-credential-summaries'

import type { QuotaCenterMode } from './use-quota-center'

function mergeQuotaBatchResponses(
  responses: readonly QuotaRuleBatchUpsertResponse[]
): QuotaRuleBatchUpsertResponse {
  return {
    succeeded: responses.flatMap((response) => response.succeeded),
    failed: responses.flatMap((response) => response.failed),
  }
}

/** 按层级路由 batch upsert：upstream 规则可能写入凭据归属团队。 */
export async function executeQuotaBatchUpsert(
  teamId: string,
  rules: QuotaRuleUpsertBody[],
  contextTeamIdByCredentialId: ReadonlyMap<string, string | null>,
  mode: QuotaCenterMode
): Promise<QuotaRuleBatchUpsertResponse> {
  const upsertBatch =
    mode === 'member'
      ? (targetTeamId: string, batch: QuotaRuleUpsertBody[]) =>
          gatewayApi.batchUpsertSelfQuotaRules(targetTeamId, batch)
      : (targetTeamId: string, batch: QuotaRuleUpsertBody[]) =>
          gatewayApi.batchUpsertQuotaRules(targetTeamId, batch)

  const nonUpstreamRules = rules.filter((rule) => rule.layer !== 'upstream')
  const upstreamRules = rules.filter((rule) => rule.layer === 'upstream')

  const upstreamByTeam = new Map<string, QuotaRuleUpsertBody[]>()
  for (const rule of upstreamRules) {
    const credId = rule.credential_id
    const targetTeamId =
      credId !== undefined && credId !== null
        ? resolveActorCredentialContextTeamId(credId, contextTeamIdByCredentialId, teamId)
        : teamId
    const existing = upstreamByTeam.get(targetTeamId) ?? []
    existing.push(rule)
    upstreamByTeam.set(targetTeamId, existing)
  }

  const responses: QuotaRuleBatchUpsertResponse[] = []
  if (nonUpstreamRules.length > 0) {
    responses.push(await upsertBatch(teamId, nonUpstreamRules))
  }
  for (const [targetTeamId, batch] of upstreamByTeam) {
    responses.push(await upsertBatch(targetTeamId, batch))
  }
  return mergeQuotaBatchResponses(responses)
}

export function collectQuotaBatchInvalidationTeamIds(
  teamId: string,
  rules: QuotaRuleUpsertBody[],
  contextTeamIdByCredentialId: ReadonlyMap<string, string | null>
): string[] {
  return collectQuotaBatchTargetTeamIds(teamId, rules, contextTeamIdByCredentialId)
}
