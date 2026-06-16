import { useMemo } from 'react'

import type { GatewayModel } from '@/api/gateway/models'
import type { QuotaRule } from '@/api/gateway/quota-rules'
import type { BudgetViewContext } from '@/features/gateway-budget/budget-match'
import {
  matchQuotaRulesForContext,
  mergeQuotaRules,
  quotaListParamsForContext,
  quotaListParamsForTeamModelPlatform,
  quotaListParamsForTeamModelUpstream,
} from '@/features/gateway-budget/quota-rule-utils'
import { useGatewayQuotaRules } from '@/features/gateway-budget/use-gateway-quota-rules'
import type { ModelInspectorScope } from '@/features/gateway-models/detail/model-inspector'

interface UseModelDetailQuotaRulesInput {
  model: GatewayModel
  scope: ModelInspectorScope
  teamId: string
  userId: string | null
}

interface UseModelDetailQuotaRulesResult {
  context: BudgetViewContext | null
  matched: QuotaRule[]
  platformRules: QuotaRule[]
  upstreamRules: QuotaRule[]
  isLoading: boolean
}

export function useModelDetailQuotaRules({
  model,
  scope,
  teamId,
  userId,
}: UseModelDetailQuotaRulesInput): UseModelDetailQuotaRulesResult {
  const isPersonal = scope === 'personal'

  const context = useMemo((): BudgetViewContext | null => {
    if (!userId) return null
    return isPersonal
      ? {
          kind: 'personal',
          userId,
          modelNames: [model.real_model],
          credentialId: model.credential_id,
        }
      : {
          kind: 'team_model',
          modelName: model.name,
          realModel: model.real_model,
          credentialId: model.credential_id,
          userId,
        }
  }, [isPersonal, model.credential_id, model.name, model.real_model, userId])

  const platformListParams = useMemo(
    () => (isPersonal ? undefined : quotaListParamsForTeamModelPlatform(model.name)),
    [isPersonal, model.name]
  )
  const upstreamListParams = useMemo(
    () =>
      model.credential_id
        ? quotaListParamsForTeamModelUpstream(model.credential_id, model.real_model)
        : undefined,
    [model.credential_id, model.real_model]
  )
  const personalListParams = useMemo(
    () => (context?.kind === 'personal' ? quotaListParamsForContext(context) : undefined),
    [context]
  )

  const platformRulesQuery = useGatewayQuotaRules(teamId, platformListParams, {
    enabled: context !== null && !isPersonal,
  })
  const upstreamRulesQuery = useGatewayQuotaRules(teamId, upstreamListParams, {
    enabled: context !== null && Boolean(model.credential_id),
  })
  const personalRulesQuery = useGatewayQuotaRules(teamId, personalListParams, {
    enabled: context?.kind === 'personal',
  })

  const rules = useMemo(
    () =>
      mergeQuotaRules(
        isPersonal ? personalRulesQuery.data : platformRulesQuery.data,
        upstreamRulesQuery.data
      ),
    [isPersonal, personalRulesQuery.data, platformRulesQuery.data, upstreamRulesQuery.data]
  )

  const isLoading =
    (isPersonal ? personalRulesQuery.isLoading : platformRulesQuery.isLoading) ||
    (Boolean(model.credential_id) && upstreamRulesQuery.isLoading)

  const matched = useMemo(
    () => (context ? matchQuotaRulesForContext(rules, context) : []),
    [context, rules]
  )

  const platformRules = useMemo(
    () => matched.filter((rule) => rule.key.layer === 'platform'),
    [matched]
  )
  const upstreamRules = useMemo(
    () => matched.filter((rule) => rule.key.layer === 'upstream'),
    [matched]
  )

  return { context, matched, platformRules, upstreamRules, isLoading }
}
