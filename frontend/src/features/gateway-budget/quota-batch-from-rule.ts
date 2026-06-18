import type { QuotaRule } from '@/api/gateway/quota-rules'

import { minutesToTimeString } from './period-reset-utils'
import {
  DEFAULT_BATCH_FORM,
  patchQuotaBatchFormForLayer,
  type QuotaBatchFormValues,
} from './quota-batch-form'

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

/** ISO 字符串 → datetime-local 输入值（本地时区，分钟精度）；空返回空串。 */
function isoToLocalDateTime(iso: string | null | undefined): string {
  if (!iso) return ''
  const parsed = new Date(iso)
  if (Number.isNaN(parsed.getTime())) return ''
  const pad = (n: number): string => String(n).padStart(2, '0')
  const year = String(parsed.getFullYear()).padStart(4, '0')
  return `${year}-${pad(parsed.getMonth() + 1)}-${pad(parsed.getDate())}T${pad(parsed.getHours())}:${pad(parsed.getMinutes())}`
}

/** 将现有 QuotaRule 反解为批量表单值，用于单条编辑预填。 */
export function quotaRuleToBatchFormValues(
  rule: QuotaRule
): { values: QuotaBatchFormValues; info: EditingRuleInfo } | null {
  const layer = rule.key.layer

  if (layer === 'platform') {
    const budgetId = rule.source_ref.budget_id
    if (!budgetId) return null

    const period = rule.key.period
    if (period !== 'daily' && period !== 'monthly' && period !== 'total') return null

    const targetKind = rule.key.target_kind
    const targetId = rule.key.target_id ?? null

    const base: QuotaBatchFormValues = {
      ...DEFAULT_BATCH_FORM,
      layer: 'platform',
      period,
      periodTimezone: rule.key.period_timezone ?? 'UTC',
      periodResetTime: minutesToTimeString(rule.key.period_reset_minutes ?? 0),
      periodResetDay: rule.key.period_reset_day ?? 1,
      allModels: rule.key.model_name === null,
      modelNames: rule.key.model_name ? [rule.key.model_name] : [],
      limit_usd: numberToStr(rule.limits.limit_usd),
      limit_tokens: numberToStr(rule.limits.limit_tokens),
      limit_requests: numberToStr(rule.limits.limit_requests),
      validFrom: isoToLocalDateTime(rule.valid_from),
      validUntil: isoToLocalDateTime(rule.valid_until),
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

    return {
      values,
      info: {
        rule,
        budgetId,
        layer,
        originalTargetId: targetId,
      },
    }
  }

  if (layer === 'upstream') {
    if (rule.source_ref.quota_id === null && rule.source_ref.budget_id === null) return null

    const values = patchQuotaBatchFormForLayer(
      {
        ...DEFAULT_BATCH_FORM,
        layer: 'upstream',
        periodTimezone: rule.key.period_timezone ?? 'UTC',
        periodResetTime: minutesToTimeString(rule.key.period_reset_minutes ?? 0),
        periodResetDay: rule.key.period_reset_day ?? 1,
        windowSeconds: String(rule.key.window_seconds ?? 0),
        quotaLabel: rule.key.quota_label ?? 'default',
        allModels: false,
        modelNames: rule.key.model_name ? [rule.key.model_name] : [],
        allCredentials: false,
        credentialIds: rule.key.credential_id ? [rule.key.credential_id] : [],
        limit_usd: numberToStr(rule.limits.limit_usd),
        limit_tokens: numberToStr(rule.limits.limit_tokens),
        limit_requests: numberToStr(rule.limits.limit_requests),
        validFrom: isoToLocalDateTime(rule.valid_from),
        validUntil: isoToLocalDateTime(rule.valid_until),
      },
      'upstream'
    )
    return {
      values,
      info: {
        rule,
        budgetId: rule.source_ref.budget_id ?? '',
        layer,
        originalTargetId: null,
      },
    }
  }

  if (rule.key.access_kind !== 'vkey') return null
  const accessId = stringOrNull(rule.key.access_id)
  if (!accessId) return null
  if (rule.source_ref.quota_id === null) return null

  const values = patchQuotaBatchFormForLayer(
    {
      ...DEFAULT_BATCH_FORM,
      layer: 'downstream',
      periodTimezone: rule.key.period_timezone ?? 'UTC',
      periodResetTime: minutesToTimeString(rule.key.period_reset_minutes ?? 0),
      periodResetDay: rule.key.period_reset_day ?? 1,
      windowSeconds: String(rule.key.window_seconds ?? 0),
      quotaLabel: rule.key.quota_label ?? 'default',
      allModels: rule.key.model_name === null,
      modelNames: rule.key.model_name ? [rule.key.model_name] : [],
      keyIds: [accessId],
      limit_usd: numberToStr(rule.limits.limit_usd),
      limit_tokens: numberToStr(rule.limits.limit_tokens),
      limit_requests: numberToStr(rule.limits.limit_requests),
      validFrom: isoToLocalDateTime(rule.valid_from),
      validUntil: isoToLocalDateTime(rule.valid_until),
    },
    'downstream'
  )
  return {
    values,
    info: {
      rule,
      budgetId: '',
      layer,
      originalTargetId: accessId,
    },
  }
}

const COPY_LABEL_SUFFIX = '-copy'

/** 复制为新配额时避免与原桶自然键碰撞。 */
function dedupeQuotaLabelForCopy(label: string): string {
  const trimmed = label.trim() || 'default'
  if (trimmed.endsWith(COPY_LABEL_SUFFIX)) {
    return `${trimmed}2`
  }
  return `${trimmed}${COPY_LABEL_SUFFIX}`
}

/**
 * 从现有规则提取维度预填，用于「复制为新配额」创建态。
 * 保留主体/凭据/模型/周期，清空限额与起止时间；upstream/downstream 的 quotaLabel 追加去重后缀。
 */
export function quotaRuleToScopePrefill(rule: QuotaRule): QuotaBatchFormValues | null {
  const parsed = quotaRuleToBatchFormValues(rule)
  if (!parsed) return null

  const { values, info } = parsed
  return {
    ...values,
    limit_usd: '',
    limit_tokens: '',
    limit_requests: '',
    validFrom: '',
    validUntil: '',
    ...(info.layer === 'upstream' || info.layer === 'downstream'
      ? { quotaLabel: dedupeQuotaLabelForCopy(values.quotaLabel) }
      : {}),
  }
}
