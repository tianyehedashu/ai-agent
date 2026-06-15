import type { QuotaRule, QuotaRuleLayer } from '@/api/gateway'
import {
  DEFAULT_BATCH_FORM,
  patchQuotaBatchFormForLayer,
  type QuotaBatchFormValues,
} from '@/features/gateway-budget/quota-batch-form'

export function isModelDetailEditableQuotaRule(rule: QuotaRule): boolean {
  const layer = rule.key.layer
  if (layer !== 'platform' && layer !== 'upstream') return false
  return rule.source_ref.budget_id !== null
}

export function buildModelQuotaDefaultForm(options: {
  modelName: string
  credentialId: string
  layer?: QuotaRuleLayer
  selfUserId?: string | null
  memberMode?: boolean
  /** upstream 层使用 real_model（非 Gateway 别名） */
  upstreamRealModel?: string
}): QuotaBatchFormValues {
  const layer = options.layer ?? 'platform'
  const upstreamModel = options.upstreamRealModel ?? options.modelName
  const base: QuotaBatchFormValues = {
    ...DEFAULT_BATCH_FORM,
    layer,
    allModels: false,
    modelNames: [layer === 'upstream' ? upstreamModel : options.modelName],
    allCredentials: false,
    credentialIds: layer === 'upstream' ? [options.credentialId] : [],
  }

  if (options.memberMode && options.selfUserId) {
    return patchQuotaBatchFormForLayer(
      {
        ...base,
        layer: 'platform',
        subjectMode: 'users',
        userIds: [options.selfUserId],
        credentialIds: options.credentialId ? [options.credentialId] : [],
      },
      'platform'
    )
  }

  if (layer === 'upstream') {
    return patchQuotaBatchFormForLayer(base, 'upstream')
  }

  return patchQuotaBatchFormForLayer(base, 'platform')
}
