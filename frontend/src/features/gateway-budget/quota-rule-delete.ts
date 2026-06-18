import { gatewayApi } from '@/api/gateway'
import type { QuotaRule } from '@/api/gateway/quota-rules'

/** 配额中心读写模式（与 use-quota-center 的 QuotaCenterMode 同义，独立声明避免循环依赖）。 */
type QuotaDeleteMode = 'admin' | 'member'

/** 该规则是否可删除：平台预算（budget_id）或 plan/upstream 配额（quota_id）。 */
export function isQuotaRuleDeletable(rule: QuotaRule): boolean {
  const ref = rule.source_ref
  return ref.budget_id !== null || ref.quota_id !== null
}

/**
 * 按规则来源删除配额：平台预算走 budget 删除，plan 配额走 plan-quota 删除。
 * 统一收口，供配额中心与模型详情复用，避免各处分别拼接删除分支。
 */
export async function deleteQuotaRule(
  teamId: string,
  rule: QuotaRule,
  mode: QuotaDeleteMode
): Promise<unknown> {
  const ref = rule.source_ref
  if (ref.budget_id !== null) {
    return mode === 'member'
      ? gatewayApi.deleteSelfQuotaRule(teamId, ref.budget_id)
      : gatewayApi.deleteBudget(teamId, ref.budget_id)
  }
  if (ref.quota_id !== null) {
    if (mode === 'member') {
      if (rule.key.layer !== 'upstream') {
        throw new Error('成员自助仅可删除本人凭据的上游配额')
      }
      return gatewayApi.deleteSelfQuotaRuleByQuotaId(teamId, ref.quota_id)
    }
    const layer = rule.key.layer === 'downstream' ? 'downstream' : 'upstream'
    return gatewayApi.deleteQuotaRule(teamId, {
      layer,
      quotaId: ref.quota_id,
      ...(layer === 'downstream' && ref.plan_id ? { planId: ref.plan_id } : {}),
    })
  }
  throw new Error('无法定位要删除的配额')
}
