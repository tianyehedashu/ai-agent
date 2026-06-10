import type { QuotaRule } from '@/api/gateway/quota-rules'

import {
  DEFAULT_BATCH_FORM,
  patchQuotaBatchFormForLayer,
  type QuotaBatchFormValues,
} from './use-quota-center'

export interface EditingRuleInfo {
  rule: QuotaRule
  budgetId: string
  layer: QuotaRule['key']['layer']
  originalTargetId: string | null
}

function stringOrNull(v: string | null | undefined): string | null {
  if (v === undefined) return null
  return v ?? null
}

function numberToStr(n: number | null | undefined): string {
  if (n === null || n === undefined) return ''
  return String(n)
}

/** 将现有 QuotaRule 反解为批量表单值，用于单条编辑预填。
 * 未匹配或不可编辑的规则返回 null。 */
export function quotaRuleToBatchFormValues(
  rule: QuotaRule
): { values: QuotaBatchFormValues; info: EditingRuleInfo } | null {
  const layer = rule.key.layer
  const budgetId = rule.source_ref.budget_id
  const period = rule.key.period
  // 仅 platform（有 budget_id）可在此面板编辑；upstream/downstream 需到凭据/Key 页。
  // 同时要求 period 明确（daily/monthly/total），否则无法写入。
  if (layer !== 'platform' || !budgetId) return null
  if (period !== 'daily' && period !== 'monthly' && period !== 'total') return null

  const targetKind = rule.key.target_kind
  const targetId = rule.key.target_id ?? null

  const base: QuotaBatchFormValues = {
    ...DEFAULT_BATCH_FORM,
    layer: 'platform',
    period,
    allModels: rule.key.model_name === null,
    modelNames: rule.key.model_name ? [rule.key.model_name] : [],
    limit_usd: numberToStr(rule.limits.limit_usd),
    limit_tokens: numberToStr(rule.limits.limit_tokens),
    limit_requests: numberToStr(rule.limits.limit_requests),
  }

  let values: QuotaBatchFormValues

  if (targetKind === 'tenant') {
    values = patchQuotaBatchFormForLayer({ ...base, subjectMode: 'tenant' }, 'platform')
  } else if (targetKind === 'user') {
    const uid = stringOrNull(rule.key.user_id ?? targetId)
    values = patchQuotaBatchFormForLayer(
      {
        ...base,
        subjectMode: 'users',
        userIds: uid ? [uid] : [],
        credentialIds: rule.key.credential_id ? [rule.key.credential_id] : [],
      },
      'platform'
    )
  } else if (targetKind === 'key') {
    const kid = stringOrNull(rule.key.access_id ?? targetId)
    values = patchQuotaBatchFormForLayer(
      {
        ...base,
        subjectMode: 'keys',
        keyIds: kid ? [kid] : [],
      },
      'platform'
    )
  } else {
    return null
  }

  const info: EditingRuleInfo = {
    rule,
    budgetId,
    layer,
    originalTargetId: targetId,
  }

  return { values, info }
}
