import { useMemo } from 'react'

import { Link } from 'react-router-dom'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Loader2 } from '@/lib/lucide-icons'

import { matchQuotaRulesForContext, type BudgetViewContext } from './budget-match'
import { budgetsAdminHref } from './paths'
import { quotaListParamsForContext, quotaRuleRowId } from './quota-rule-utils'
import { QuotaUsageRow } from './quota-usage-row'
import { useGatewayQuotaRules } from './use-gateway-quota-rules'

export interface BudgetUsageCardProps {
  teamId: string
  context: BudgetViewContext
  /** 可链到配额中心 / 我的配额（admin 或自助成员） */
  manageHref?: string
  /** 链接文案，默认「在配额中心配置 →」 */
  manageLabel?: string
  className?: string
  /** 关联模型列表加载中（凭据详情页避免闪「暂无预算」） */
  modelsLoading?: boolean
}

export function BudgetUsageCard({
  teamId,
  context,
  manageHref,
  manageLabel = '在配额中心配置 →',
  className,
  modelsLoading = false,
}: BudgetUsageCardProps): React.JSX.Element {
  const listParams = useMemo(() => quotaListParamsForContext(context), [context])
  const { data: rules, isLoading: rulesLoading } = useGatewayQuotaRules(teamId, listParams)
  const matched = useMemo(() => matchQuotaRulesForContext(rules ?? [], context), [rules, context])
  const isLoading = rulesLoading || modelsLoading

  return (
    <Card className={className}>
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <CardTitle className="text-base">配额规则</CardTitle>
            <CardDescription>
              平台预算、上游厂商额度与下游权益；各层级独立计量与拦截。
            </CardDescription>
          </div>
          {manageHref ? (
            <Link to={manageHref} className="text-xs text-primary hover:underline">
              {manageLabel}
            </Link>
          ) : null}
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {isLoading ? (
          <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            加载配额…
          </div>
        ) : null}
        {!isLoading && matched.length === 0 ? (
          <p className="text-sm text-muted-foreground">暂无针对此资源的限额，请联系团队管理员。</p>
        ) : null}
        {matched.map((rule) => (
          <QuotaUsageRow key={quotaRuleRowId(rule)} rule={rule} />
        ))}
      </CardContent>
    </Card>
  )
}

export function BudgetUsageCardWithAdminLink(
  props: Omit<BudgetUsageCardProps, 'manageHref' | 'manageLabel'> & {
    isAdmin: boolean
    /** 非管理员但拥有该凭据：可自助到「我的配额」设限 */
    canSelfManage?: boolean
    modelPrefill?: string
    credentialPrefill?: string
    layerPrefill?: 'platform' | 'upstream' | 'downstream'
  }
): React.JSX.Element {
  const { isAdmin, canSelfManage, modelPrefill, credentialPrefill, layerPrefill, teamId, ...rest } =
    props
  const href =
    isAdmin || canSelfManage
      ? budgetsAdminHref(teamId, {
          model: modelPrefill,
          credential: credentialPrefill,
          layer: isAdmin ? layerPrefill : 'platform',
        })
      : undefined
  const label = isAdmin ? '在配额中心配置 →' : '设置我的限额 →'
  return <BudgetUsageCard teamId={teamId} manageHref={href} manageLabel={label} {...rest} />
}
