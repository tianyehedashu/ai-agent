import { useMemo } from 'react'

import { useQuery } from '@tanstack/react-query'

import { gatewayApi } from '@/api/gateway'
import {
  BudgetUsageCard,
  BudgetUsageCardWithAdminLink,
} from '@/features/gateway-budget/budget-usage-card'
import { useGatewayTeamId } from '@/hooks/use-gateway-team-id'

export interface CredentialBudgetSectionProps {
  credentialId: string
  userId: string
  isAdmin: boolean
}

/** 团队/个人凭据详情：按关联模型名匹配 tenant/user 预算。 */
export function CredentialBudgetSection({
  credentialId,
  userId,
  isAdmin,
}: CredentialBudgetSectionProps): React.JSX.Element {
  const teamId = useGatewayTeamId()
  const { data: models = [] } = useQuery({
    queryKey: ['gateway', 'models', teamId, 'credential-budget', credentialId],
    queryFn: () =>
      gatewayApi.listModels(teamId, {
        registry_scope: 'team',
        credential_id: credentialId,
      }),
    enabled: credentialId.length > 0 && teamId.length > 0,
  })

  const linkedModelNames = useMemo(() => models.map((m) => m.name), [models])
  const modelPrefill = linkedModelNames[0]

  return (
    <BudgetUsageCardWithAdminLink
      teamId={teamId}
      isAdmin={isAdmin}
      modelPrefill={modelPrefill}
      context={{
        kind: 'credential',
        userId,
        linkedModelNames,
      }}
    />
  )
}

export interface PersonalCredentialBudgetSectionProps {
  credentialId: string
  userId: string
  provider: string
}

/** 个人凭据：仅展示当前用户的 user 级预算。 */
export function PersonalCredentialBudgetSection({
  credentialId,
  userId,
  provider,
}: PersonalCredentialBudgetSectionProps): React.JSX.Element {
  const teamId = useGatewayTeamId()
  const { data: myModels = [] } = useQuery({
    queryKey: ['gateway', 'my-models'],
    queryFn: () => gatewayApi.listMyModels(),
  })

  const linkedModelNames = useMemo(() => {
    void credentialId
    return myModels.filter((m) => m.provider === provider).map((m) => m.model_id)
  }, [myModels, provider, credentialId])

  return (
    <BudgetUsageCard
      teamId={teamId}
      context={{
        kind: 'personal',
        userId,
        modelNames: linkedModelNames,
      }}
    />
  )
}
