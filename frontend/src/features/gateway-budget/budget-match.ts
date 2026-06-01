import type { GatewayBudget } from '@/api/gateway/budgets'

export type BudgetViewContext =
  | { kind: 'personal'; userId: string; modelNames?: string[] }
  | { kind: 'team_model'; modelName: string; userId?: string }
  | { kind: 'credential'; userId: string; linkedModelNames: string[]; credentialId?: string }
  | { kind: 'virtual_key'; keyId: string }

function modelMatchesBudget(budget: GatewayBudget, modelNames: string[]): boolean {
  if (budget.model_name === null || budget.model_name === '') {
    return true
  }
  if (modelNames.length === 0) {
    return false
  }
  return modelNames.includes(budget.model_name)
}

function modelMatchesSingle(budget: GatewayBudget, modelName: string): boolean {
  if (budget.model_name === null || budget.model_name === '') {
    return true
  }
  return budget.model_name === modelName
}

/** @deprecated 嵌入页请改用 matchQuotaRulesForContext */
export function matchBudgetsForContext(
  budgets: GatewayBudget[],
  ctx: BudgetViewContext
): GatewayBudget[] {
  switch (ctx.kind) {
    case 'personal':
      return budgets.filter((b) => {
        if (b.target_kind !== 'user' || b.target_id !== ctx.userId) {
          return false
        }
        const names = ctx.modelNames ?? []
        if (names.length === 0) {
          return b.model_name === null || b.model_name === ''
        }
        return modelMatchesBudget(b, names)
      })
    case 'team_model':
      return budgets.filter((b) => {
        if (b.target_kind === 'tenant') {
          return modelMatchesSingle(b, ctx.modelName)
        }
        if (b.target_kind === 'user' && ctx.userId !== undefined && b.target_id === ctx.userId) {
          return modelMatchesSingle(b, ctx.modelName)
        }
        return false
      })
    case 'credential':
      return budgets.filter((b) => {
        if (b.target_kind === 'tenant') {
          return modelMatchesBudget(b, ctx.linkedModelNames)
        }
        if (b.target_kind === 'user' && b.target_id === ctx.userId) {
          return modelMatchesBudget(b, ctx.linkedModelNames)
        }
        return false
      })
    case 'virtual_key':
      return budgets.filter((b) => b.target_kind === 'key' && b.target_id === ctx.keyId)
  }
}

export { matchQuotaRulesForContext } from './quota-rule-utils'
