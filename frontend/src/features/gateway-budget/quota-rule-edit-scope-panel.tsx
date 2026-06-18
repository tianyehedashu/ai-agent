import type { QuotaRule } from '@/api/gateway/quota-rules'
import {
  formatQuotaRuleInvokeNameLabel,
  formatQuotaRulePeriod,
  formatQuotaRulePeriodWindow,
  formatQuotaRuleUpstreamNameLabel,
  isQuotaRuleSubjectApplicable,
  resolveQuotaRuleCredentialLabel,
  resolveQuotaRuleSubjectLabel,
  type QuotaRuleLabelContext,
} from '@/features/gateway-budget/quota-rule-utils'
import { QuotaUsageInlineEditor } from '@/features/gateway-budget/quota-usage-inline-editor'
import type { QuotaCenterMode } from '@/features/gateway-budget/use-quota-center'
import { isQuotaRuleUsageAdjustable } from '@/features/gateway-budget/use-quota-usage-adjust'

interface QuotaRuleEditScopePanelProps {
  rule: QuotaRule
  teamId: string
  mode: QuotaCenterMode
  labelContext: QuotaRuleLabelContext
  canAdjustUsage: boolean
}

export function QuotaRuleEditScopePanel({
  rule,
  teamId,
  mode,
  labelContext,
  canAdjustUsage,
}: QuotaRuleEditScopePanelProps): React.JSX.Element {
  const invokeLabel = formatQuotaRuleInvokeNameLabel(rule, labelContext)
  const upstreamLabel = formatQuotaRuleUpstreamNameLabel(rule, labelContext)
  const periodWindow = formatQuotaRulePeriodWindow(rule)
  const limitUsd = rule.limits.limit_usd
  const limitTok = rule.limits.limit_tokens

  return (
    <div className="space-y-4 rounded-lg border bg-muted/20 p-4">
      <div>
        <p className="text-sm font-medium">当前规则</p>
        <p className="mt-1 text-xs text-muted-foreground">
          编辑模式下仅可修改限额与本周期用量，维度（主体 / 凭据 / 模型）不可变更。
        </p>
      </div>

      <dl className="grid gap-2 text-xs sm:grid-cols-2">
        <div>
          <dt className="text-muted-foreground">层级</dt>
          <dd className="mt-0.5 font-medium">
            {rule.key.layer === 'platform' ? '平台护栏' : '上游额度'}
          </dd>
        </div>
        {isQuotaRuleSubjectApplicable(rule) ? (
          <div>
            <dt className="text-muted-foreground">主体</dt>
            <dd className="mt-0.5 font-medium">
              {resolveQuotaRuleSubjectLabel(rule, labelContext)}
            </dd>
          </div>
        ) : null}
        <div>
          <dt className="text-muted-foreground">凭据</dt>
          <dd className="mt-0.5 font-medium">
            {resolveQuotaRuleCredentialLabel(rule, labelContext)}
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">周期</dt>
          <dd className="mt-0.5 font-medium">{formatQuotaRulePeriod(rule)}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">调用名</dt>
          <dd className="mt-0.5 truncate font-medium" title={invokeLabel}>
            {invokeLabel}
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">上游模型</dt>
          <dd className="mt-0.5 truncate font-mono text-muted-foreground" title={upstreamLabel}>
            {upstreamLabel}
          </dd>
        </div>
      </dl>

      {periodWindow ? <p className="text-[11px] text-muted-foreground">{periodWindow}</p> : null}

      {canAdjustUsage && isQuotaRuleUsageAdjustable(rule) ? (
        <div className="border-t pt-3">
          <p className="mb-2 text-xs font-medium">本周期已用</p>
          <QuotaUsageInlineEditor
            rule={rule}
            teamId={teamId}
            mode={mode}
            canEdit
            limitUsd={limitUsd}
            limitTok={limitTok}
          />
        </div>
      ) : rule.usage ? (
        <p className="text-xs text-muted-foreground">当前周期暂无可用用量校正入口。</p>
      ) : null}
    </div>
  )
}
