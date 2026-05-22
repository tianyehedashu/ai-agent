import { useMemo } from 'react'

import type { GatewayBudget } from '@/api/gateway/budgets'
import type { PersonalGatewayModel } from '@/api/gateway/my-models'

import { matchBudgetsForContext } from './budget-match'
import { PersonalCredentialBudgetBadges } from './personal-credential-budget-badges'

export interface PersonalCredentialBudgetInlineProps {
  userId: string
  credentialId: string
  budgets: GatewayBudget[]
  myModels: PersonalGatewayModel[]
}

/** 个人凭据列表行内：按 credential_id 关联模型匹配 user 级预算（轻量 Badge）。 */
export function PersonalCredentialBudgetInline({
  userId,
  credentialId,
  budgets,
  myModels,
}: PersonalCredentialBudgetInlineProps): React.JSX.Element {
  const linkedModelNames = useMemo(
    () => myModels.filter((m) => m.credential_id === credentialId).map((m) => m.model_id),
    [myModels, credentialId]
  )

  const matched = useMemo(
    () =>
      matchBudgetsForContext(budgets, {
        kind: 'personal',
        userId,
        modelNames: linkedModelNames,
      }),
    [budgets, userId, linkedModelNames]
  )

  return <PersonalCredentialBudgetBadges budgets={matched} />
}
