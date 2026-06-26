import type { GatewayBudget } from '@/api/gateway/budgets'

export interface BudgetUsageMetrics {
  usdRatio: number
  tokRatio: number
  imgRatio: number
  ratio: number
  softRatio: number
  barColor: string
}

export function computeBudgetUsageMetrics(budget: GatewayBudget): BudgetUsageMetrics {
  const limitUsd = budget.limit_usd ?? null
  const softUsd = budget.soft_limit_usd ?? null
  const limitTok = budget.limit_tokens ?? null
  const limitImg = budget.limit_images ?? null
  const usdRatio = limitUsd !== null && limitUsd > 0 ? budget.current_usd / limitUsd : 0
  const tokRatio = limitTok !== null && limitTok > 0 ? budget.current_tokens / limitTok : 0
  const imgRatio = limitImg !== null && limitImg > 0 ? budget.current_images / limitImg : 0
  const ratio = Math.max(usdRatio, tokRatio, imgRatio)
  const softRatio =
    softUsd !== null && softUsd > 0 && limitUsd !== null && limitUsd > 0
      ? budget.current_usd / softUsd
      : 0
  const barColor =
    ratio >= 1
      ? 'bg-destructive'
      : ratio >= 0.9 || softRatio >= 1
        ? 'bg-amber-500'
        : 'bg-emerald-500'
  return { usdRatio, tokRatio, imgRatio, ratio, softRatio, barColor }
}

export function formatBudgetPeriod(period: GatewayBudget['period']): string {
  switch (period) {
    case 'daily':
      return '每日'
    case 'monthly':
      return '每月'
    case 'total':
      return '总额'
    default:
      return period
  }
}

export function formatBudgetTargetKind(kind: GatewayBudget['target_kind']): string {
  switch (kind) {
    case 'tenant':
      return '团队'
    case 'user':
      return '用户'
    case 'key':
      return '虚拟 Key'
    case 'system':
      return '系统'
    default:
      return kind
  }
}

export function formatBudgetResetAt(budget: GatewayBudget): string {
  if (budget.budget_reset_at) {
    return new Date(budget.budget_reset_at).toLocaleString()
  }
  if (budget.reset_at) {
    return new Date(budget.reset_at).toLocaleDateString()
  }
  return '—'
}
