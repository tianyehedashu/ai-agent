import type { QuotaRuleLayer } from '@/api/gateway'

export interface QuotaBatchFormValues {
  layer: QuotaRuleLayer
  subjectMode: 'tenant' | 'users' | 'keys'
  userIds: string[]
  keyIds: string[]
  credentialIds: string[]
  modelNames: string[]
  allModels: boolean
  allCredentials: boolean
  period: 'daily' | 'monthly' | 'total'
  periodTimezone: string
  periodResetTime: string
  periodResetDay: number
  windowSeconds: string
  quotaLabel: string
  limit_usd: string
  limit_tokens: string
  limit_requests: string
  /** 起止时间（datetime-local 字符串）；空表示该侧不限 */
  validFrom: string
  validUntil: string
}

export const DEFAULT_BATCH_FORM: QuotaBatchFormValues = {
  layer: 'platform',
  subjectMode: 'tenant',
  userIds: [],
  keyIds: [],
  credentialIds: [],
  modelNames: [],
  allModels: true,
  allCredentials: true,
  period: 'monthly',
  periodTimezone: 'UTC',
  periodResetTime: '00:00',
  periodResetDay: 1,
  windowSeconds: '0',
  quotaLabel: 'default',
  limit_usd: '',
  limit_tokens: '',
  limit_requests: '',
  validFrom: '',
  validUntil: '',
}

/** 切换层级时清理与当前层级无关的字段，避免预览条数异常 */
export function patchQuotaBatchFormForLayer(
  values: QuotaBatchFormValues,
  layer: QuotaRuleLayer
): QuotaBatchFormValues {
  if (layer === 'platform') {
    const subjectMode = values.subjectMode
    return {
      ...values,
      layer,
      subjectMode,
      credentialIds: subjectMode === 'users' ? values.credentialIds : [],
      userIds: subjectMode === 'users' ? values.userIds : [],
      keyIds: subjectMode === 'keys' ? values.keyIds : [],
    }
  }
  if (layer === 'upstream') {
    return {
      ...values,
      layer,
      subjectMode: 'tenant',
      userIds: [],
      keyIds: [],
    }
  }
  return {
    ...values,
    layer,
    subjectMode: 'keys',
    userIds: [],
    credentialIds: [],
  }
}

export function patchQuotaBatchFormForSubjectMode(
  values: QuotaBatchFormValues,
  subjectMode: QuotaBatchFormValues['subjectMode']
): QuotaBatchFormValues {
  return {
    ...values,
    subjectMode,
    userIds: subjectMode === 'users' ? values.userIds : [],
    keyIds: subjectMode === 'keys' ? values.keyIds : [],
    credentialIds: subjectMode === 'users' ? values.credentialIds : [],
  }
}

export function expandBatchFormValues(
  values: QuotaBatchFormValues,
  credentialIds: readonly string[]
): QuotaBatchFormValues {
  if (values.layer === 'upstream' && values.allCredentials) {
    return {
      ...values,
      allCredentials: false,
      credentialIds: [...credentialIds],
    }
  }
  return values
}
