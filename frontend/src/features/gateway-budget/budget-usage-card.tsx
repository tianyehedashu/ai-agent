import { useMemo } from 'react'

import { Link } from 'react-router-dom'

import type { GatewayBudget } from '@/api/gateway/budgets'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Loader2 } from '@/lib/lucide-icons'

import { matchBudgetsForContext, type BudgetViewContext } from './budget-match'
import {
  computeBudgetUsageMetrics,
  formatBudgetPeriod,
  formatBudgetResetAt,
  formatBudgetTargetKind,
} from './budget-progress-utils'
import { budgetsAdminHref } from './paths'
import { useGatewayBudgets } from './use-gateway-budgets'

export interface BudgetUsageCardProps {
  teamId: string
  context: BudgetViewContext
  /** Admin 在资源详情页可链到专页 */
  adminManageHref?: string
  className?: string
  /** 关联模型列表加载中（凭据详情页避免闪「暂无预算」） */
  modelsLoading?: boolean
}

function BudgetUsageRow({ budget }: { budget: GatewayBudget }): React.JSX.Element {
  const { ratio, barColor } = computeBudgetUsageMetrics(budget)
  const limitUsd = budget.limit_usd ?? null
  const softUsd = budget.soft_limit_usd ?? null
  const limitTok = budget.limit_tokens ?? null

  return (
    <div className="space-y-2 rounded-md border border-border/60 bg-muted/20 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
        <span className="font-medium">
          {formatBudgetTargetKind(budget.target_kind)} · {formatBudgetPeriod(budget.period)}
        </span>
        <span className="text-muted-foreground">
          {budget.model_name ?? '全模型'} · 重置 {formatBudgetResetAt(budget)}
        </span>
      </div>
      <div className="space-y-0.5 text-xs tabular-nums">
        <div>
          USD {budget.current_usd.toFixed(4)} /{' '}
          {limitUsd !== null ? `$${limitUsd.toFixed(2)}` : '∞'}
          {softUsd !== null ? (
            <span className="text-muted-foreground"> · 软限 ${softUsd.toFixed(2)}</span>
          ) : null}
        </div>
        <div>
          Token {budget.current_tokens} / {limitTok ?? '∞'}
        </div>
        {budget.limit_requests !== null ? (
          <div>
            请求 {budget.current_requests} / {budget.limit_requests}
          </div>
        ) : null}
      </div>
      <div className="flex items-center gap-2">
        <div className="h-2 flex-1 overflow-hidden rounded bg-muted">
          <div
            className={`h-full ${barColor}`}
            style={{ width: `${Math.min(100, (ratio > 0 ? ratio : 0) * 100).toFixed(1)}%` }}
          />
        </div>
        <span className="text-xs tabular-nums">{(ratio * 100).toFixed(1)}%</span>
      </div>
    </div>
  )
}

export function BudgetUsageCard({
  teamId,
  context,
  adminManageHref,
  className,
  modelsLoading = false,
}: BudgetUsageCardProps): React.JSX.Element {
  const { data: budgets, isLoading: budgetsLoading } = useGatewayBudgets(teamId)
  const matched = useMemo(() => matchBudgetsForContext(budgets ?? [], context), [budgets, context])
  const isLoading = budgetsLoading || modelsLoading

  return (
    <Card className={className}>
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <CardTitle className="text-base">平台预算（Gateway）</CardTitle>
            <CardDescription>
              团队/用户/Key 在 Gateway 侧的消费护栏，与厂商套餐、客户权益相互独立。
            </CardDescription>
          </div>
          {adminManageHref ? (
            <Link to={adminManageHref} className="text-xs text-primary hover:underline">
              在预算管理中配置 →
            </Link>
          ) : null}
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {isLoading ? (
          <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            加载预算…
          </div>
        ) : null}
        {!isLoading && matched.length === 0 ? (
          <p className="text-sm text-muted-foreground">暂无针对此资源的限额，请联系团队管理员。</p>
        ) : null}
        {matched.map((b) => (
          <BudgetUsageRow key={b.id} budget={b} />
        ))}
      </CardContent>
    </Card>
  )
}

export function BudgetUsageCardWithAdminLink(
  props: Omit<BudgetUsageCardProps, 'adminManageHref'> & {
    isAdmin: boolean
    modelPrefill?: string
  }
): React.JSX.Element {
  const { isAdmin, modelPrefill, teamId, ...rest } = props
  const adminHref = isAdmin
    ? budgetsAdminHref(teamId, {
        model: modelPrefill,
      })
    : undefined
  return <BudgetUsageCard teamId={teamId} adminManageHref={adminHref} {...rest} />
}
