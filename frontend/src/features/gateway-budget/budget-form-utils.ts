import type { BudgetUpsertBody } from '@/api/gateway/budgets'

export function parseOptionalInt(raw: string): number | null {
  const t = raw.trim()
  if (t === '') return null
  const n = Number.parseInt(t, 10)
  return Number.isFinite(n) && n >= 0 ? n : null
}

export function parseOptionalUsd(raw: string): number | null {
  const t = raw.trim()
  if (t === '') return null
  const n = Number.parseFloat(t)
  return Number.isFinite(n) && n >= 0 ? n : null
}

export interface BudgetFormValues {
  target_kind: BudgetUpsertBody['target_kind']
  target_id: string
  period: BudgetUpsertBody['period']
  model_name: string
  limit_usd: string
  soft_limit_usd: string
  limit_tokens: string
  limit_requests: string
}

export const DEFAULT_BUDGET_FORM_VALUES: BudgetFormValues = {
  target_kind: 'tenant',
  target_id: '',
  period: 'monthly',
  model_name: '',
  limit_usd: '100',
  soft_limit_usd: '80',
  limit_tokens: '',
  limit_requests: '',
}

export function budgetFormValuesFromBudget(budget: {
  target_kind: BudgetUpsertBody['target_kind']
  target_id: string | null
  period: BudgetUpsertBody['period']
  model_name: string | null
  limit_usd: number | null
  soft_limit_usd?: number | null
  limit_tokens: number | null
  limit_requests: number | null
}): BudgetFormValues {
  return {
    target_kind: budget.target_kind,
    target_id: budget.target_id ?? '',
    period: budget.period,
    model_name: budget.model_name ?? '',
    limit_usd: budget.limit_usd !== null ? String(budget.limit_usd) : '',
    soft_limit_usd:
      budget.soft_limit_usd !== null && budget.soft_limit_usd !== undefined
        ? String(budget.soft_limit_usd)
        : '',
    limit_tokens: budget.limit_tokens !== null ? String(budget.limit_tokens) : '',
    limit_requests: budget.limit_requests !== null ? String(budget.limit_requests) : '',
  }
}

export function buildBudgetUpsertBody(values: BudgetFormValues): BudgetUpsertBody | null {
  const modelTrim = values.model_name.trim()
  const body: BudgetUpsertBody = {
    target_kind: values.target_kind,
    period: values.period,
  }
  if (modelTrim !== '') {
    body.model_name = modelTrim
  }
  const targetTrim = values.target_id.trim()
  if (values.target_kind === 'user' || values.target_kind === 'key') {
    if (targetTrim === '') {
      return null
    }
    body.target_id = targetTrim
  }
  const lu = parseOptionalUsd(values.limit_usd)
  const ls = parseOptionalUsd(values.soft_limit_usd)
  const lt = parseOptionalInt(values.limit_tokens)
  const lr = parseOptionalInt(values.limit_requests)
  if (lu !== null) body.limit_usd = lu
  if (ls !== null) body.soft_limit_usd = ls
  if (lt !== null) body.limit_tokens = lt
  if (lr !== null) body.limit_requests = lr
  if (lu === null && lt === null && lr === null) {
    return null
  }
  return body
}
