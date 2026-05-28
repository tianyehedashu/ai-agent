import type { GatewayBudget } from '@/api/gateway/budgets'
import type { PersonalGatewayModel } from '@/api/gateway/my-models'

import { PersonalCredentialBudgetBadges } from './personal-credential-budget-badges'

export interface PersonalCredentialBudgetInlineProps {
  userId: string
  credentialId: string
  budgets: GatewayBudget[]
  myModels: PersonalGatewayModel[]
}

function filterPersonalUserBudgets(
  budgets: GatewayBudget[],
  userId: string,
  modelNames: string[]
): GatewayBudget[] {
  return budgets.filter((b) => {
    if (b.target_kind !== 'user' || b.target_id !== userId) return false
    if (modelNames.length === 0) return b.model_name === null || b.model_name === ''
    if (b.model_name === null || b.model_name === '') return true
    return modelNames.includes(b.model_name)
  })
}

/** 个人凭据列表行内：按 credential_id 关联模型匹配 user 级预算（轻量 Badge）。 */
export function PersonalCredentialBudgetInline({
  userId,
  credentialId,
  budgets,
  myModels,
}: PersonalCredentialBudgetInlineProps): React.JSX.Element {
  const linkedModelNames = myModels
    .filter((m) => m.credential_id === credentialId)
    .map((m) => m.model_id)

  const matched = filterPersonalUserBudgets(budgets, userId, linkedModelNames)

  return <PersonalCredentialBudgetBadges budgets={matched} />
}
