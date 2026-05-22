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

/** 团队凭据详情：按 credential_id 关联模型匹配 tenant/user 预算。 */
export function CredentialBudgetSection({
  credentialId,
  userId,
  isAdmin,
}: CredentialBudgetSectionProps): React.JSX.Element {
  const teamId = useGatewayTeamId()
  const { data: models = [], isLoading: modelsLoading } = useQuery({
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
  const budgetContext = useMemo(
    () => ({
      kind: 'credential' as const,
      userId,
      linkedModelNames,
    }),
    [userId, linkedModelNames]
  )

  return (
    <BudgetUsageCardWithAdminLink
      teamId={teamId}
      isAdmin={isAdmin}
      modelPrefill={modelPrefill}
      context={budgetContext}
      modelsLoading={modelsLoading}
    />
  )
}

export interface PersonalCredentialBudgetSectionProps {
  credentialId: string
  userId: string
}

/** 个人凭据详情：按 credential_id 关联模型匹配 user 级预算。 */
export function PersonalCredentialBudgetSection({
  credentialId,
  userId,
}: PersonalCredentialBudgetSectionProps): React.JSX.Element {
  const teamId = useGatewayTeamId()
  const { data: myModels = [], isLoading: modelsLoading } = useQuery({
    queryKey: ['gateway', 'my-models'],
    queryFn: () => gatewayApi.listMyModels(),
  })

  const linkedModelNames = useMemo(
    () => myModels.filter((m) => m.credential_id === credentialId).map((m) => m.model_id),
    [myModels, credentialId]
  )
  const budgetContext = useMemo(
    () => ({
      kind: 'personal' as const,
      userId,
      modelNames: linkedModelNames,
    }),
    [userId, linkedModelNames]
  )

  return <BudgetUsageCard teamId={teamId} context={budgetContext} modelsLoading={modelsLoading} />
}
