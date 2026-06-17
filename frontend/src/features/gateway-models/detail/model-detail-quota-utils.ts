import type { QuotaRule, QuotaRuleLayer } from '@/api/gateway'
import {
  DEFAULT_BATCH_FORM,
  patchQuotaBatchFormForLayer,
  type QuotaBatchFormValues,
} from '@/features/gateway-budget/quota-batch-form'

export function isModelDetailEditableQuotaRule(rule: QuotaRule): boolean {
  const layer = rule.key.layer
  if (layer === 'platform') {
    return rule.source_ref.budget_id !== null
  }
  if (layer === 'upstream') {
    return (
      rule.source_ref.budget_id !== null ||
      (rule.source_ref.plan_id !== null && rule.source_ref.quota_id !== null)
    )
  }
  return false
}

/** 模型详情行级写权限：管理员可改全部；成员仅可改本人护栏 / 本人凭据上的厂商额度。 */
export function canEditQuotaRuleOnModelDetail(
  rule: QuotaRule,
  options: {
    isAdmin: boolean
    userId: string | null
    /** 当前模型绑定凭据的 created_by_user_id */
    credentialOwnerId?: string | null
  }
): boolean {
  if (!isModelDetailEditableQuotaRule(rule)) return false
  if (options.isAdmin) return true
  if (!options.userId) return false

  if (rule.key.layer === 'platform') {
    return rule.key.target_kind === 'user' && rule.key.user_id === options.userId
  }
  if (rule.key.layer === 'upstream') {
    const ownerId = options.credentialOwnerId ?? null
    return ownerId !== null && ownerId === options.userId
  }
  return false
}

export function canCreateUpstreamQuotaOnModelDetail(options: {
  isAdmin: boolean
  userId: string | null
  credentialId: string
  credentialOwnerId?: string | null
}): boolean {
  if (!options.credentialId || !options.userId) return false
  if (options.isAdmin) return true
  const ownerId = options.credentialOwnerId ?? null
  return ownerId !== null && ownerId === options.userId
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
