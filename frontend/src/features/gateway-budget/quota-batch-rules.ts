import type { QuotaRuleUpsertBody } from '@/api/gateway'

import { parseOptionalInt, parseOptionalUsd } from './budget-form-utils'
import { periodResetMinutesFromTime } from './period-reset-fields'

import type { QuotaBatchFormValues } from './quota-batch-form'

export type RealModelsByCredential = ReadonlyMap<string, readonly string[]>

function applyPeriodResetToBody(body: QuotaRuleUpsertBody, values: QuotaBatchFormValues): void {
  const minutes = periodResetMinutesFromTime(values.periodResetTime)
  if (values.layer === 'platform') {
    body.period_timezone = values.periodTimezone
    body.period_reset_minutes = minutes
    if (values.period === 'monthly') {
      body.period_reset_day = values.periodResetDay
    }
    return
  }
  body.reset_timezone = values.periodTimezone
  body.reset_time_minutes = minutes
  if (values.windowSeconds === '2592000') {
    body.reset_day_of_month = values.periodResetDay
  }
  if (values.windowSeconds === '86400') {
    body.reset_strategy = 'calendar_daily_utc'
  } else if (values.windowSeconds === '2592000') {
    body.reset_strategy = 'calendar_monthly_utc'
  }
}

/** datetime-local（无时区，本地时间）→ ISO 字符串；空串返回 null（= 该侧不限）。 */
function localDateTimeToIso(value: string): string | null {
  const trimmed = value.trim()
  if (!trimmed) return null
  const parsed = new Date(trimmed)
  if (Number.isNaN(parsed.getTime())) return null
  return parsed.toISOString()
}

function applyValidityToBody(body: QuotaRuleUpsertBody, values: QuotaBatchFormValues): void {
  body.valid_from = localDateTimeToIso(values.validFrom)
  body.valid_until = localDateTimeToIso(values.validUntil)
}

export interface BuildBatchRulesOptions {
  /** 上游层：凭据 id → 已注册 real_model 列表；用于过滤非法笛卡尔积 */
  realModelsByCredential?: RealModelsByCredential
}

/** 从团队/个人模型列表构建 upstream 凭据→real_model 映射 */
export function buildRealModelsByCredentialMap(input: {
  teamModels?: readonly { credential_id: string; real_model: string }[]
  personalModels?: readonly { credential_id: string; model_id: string }[]
}): RealModelsByCredential {
  const map = new Map<string, Set<string>>()
  const add = (credId: string, realModel: string): void => {
    const trimmed = realModel.trim()
    if (!trimmed) return
    let set = map.get(credId)
    if (!set) {
      set = new Set()
      map.set(credId, set)
    }
    set.add(trimmed)
  }
  for (const model of input.teamModels ?? []) {
    add(model.credential_id, model.real_model)
  }
  for (const model of input.personalModels ?? []) {
    add(model.credential_id, model.model_id)
  }
  const result = new Map<string, readonly string[]>()
  for (const [credId, set] of map) {
    result.set(credId, [...set])
  }
  return result
}

export function upstreamModelAllowedOnCredential(
  credId: string,
  model: string | null,
  realModelsByCredential?: RealModelsByCredential
): boolean {
  if (model === null) return true
  // 无映射时不过滤，由后端 _assert_real_model_on_credential 兜底
  if (!realModelsByCredential) return true
  const allowed = realModelsByCredential.get(credId)
  return allowed?.includes(model) ?? false
}

/** 将批量表单展开为 upsert 规则列表；至少一项限额且主体/模型有效。 */
export function buildBatchRules(
  values: QuotaBatchFormValues,
  options?: BuildBatchRulesOptions
): QuotaRuleUpsertBody[] | null {
  const lu = parseOptionalUsd(values.limit_usd)
  const lt = parseOptionalInt(values.limit_tokens)
  const lr = parseOptionalInt(values.limit_requests)
  if (lu === null && lt === null && lr === null) return null

  const models = values.allModels ? [null] : values.modelNames.map((m) => m || null)
  if (!values.allModels && models.length === 0) return null

  const rules: QuotaRuleUpsertBody[] = []

  if (values.layer === 'platform') {
    const subjects: { target_kind: QuotaRuleUpsertBody['target_kind']; target_id?: string }[] = []
    if (values.subjectMode === 'tenant') {
      subjects.push({ target_kind: 'tenant' })
    } else if (values.subjectMode === 'users') {
      for (const uid of values.userIds) {
        subjects.push({ target_kind: 'user', target_id: uid })
      }
    } else {
      for (const kid of values.keyIds) {
        subjects.push({ target_kind: 'key', target_id: kid })
      }
    }
    if (subjects.length === 0) return null
    for (const sub of subjects) {
      const credTargets =
        sub.target_kind === 'user' && values.credentialIds.length > 0
          ? values.credentialIds
          : [null]
      for (const credId of credTargets) {
        for (const model of models) {
          const body: QuotaRuleUpsertBody = {
            layer: 'platform',
            target_kind: sub.target_kind,
            period: values.period,
          }
          if (sub.target_id) body.target_id = sub.target_id
          if (credId) body.credential_id = credId
          if (model) body.model_name = model
          if (lu !== null) body.limit_usd = lu
          if (lt !== null) body.limit_tokens = lt
          if (lr !== null) body.limit_requests = lr
          applyPeriodResetToBody(body, values)
          applyValidityToBody(body, values)
          rules.push(body)
        }
      }
    }
    return rules
  }

  if (values.layer === 'upstream') {
    const creds = values.allCredentials ? [] : values.credentialIds
    if (!values.allCredentials && creds.length === 0) return null
    const credentialTargets = values.allCredentials ? [null] : creds
    const ws = parseOptionalInt(values.windowSeconds) ?? 0
    const realModelsByCredential = options?.realModelsByCredential
    for (const credId of credentialTargets) {
      if (credId === null) continue
      for (const model of models) {
        if (!upstreamModelAllowedOnCredential(credId, model, realModelsByCredential)) {
          continue
        }
        const body: QuotaRuleUpsertBody = {
          layer: 'upstream',
          window_seconds: ws,
          quota_label: values.quotaLabel.trim() || 'default',
        }
        body.credential_id = credId
        if (model) body.model_name = model
        if (lu !== null) body.limit_usd = lu
        if (lt !== null) body.limit_tokens = lt
        if (lr !== null) body.limit_requests = lr
        applyPeriodResetToBody(body, values)
        applyValidityToBody(body, values)
        rules.push(body)
      }
    }
    return rules.length > 0 ? rules : null
  }

  const ws = parseOptionalInt(values.windowSeconds) ?? 0
  if (values.keyIds.length === 0) return null
  for (const kid of values.keyIds) {
    for (const model of models) {
      const body: QuotaRuleUpsertBody = {
        layer: 'downstream',
        access_kind: 'vkey',
        access_id: kid,
        window_seconds: ws,
        quota_label: values.quotaLabel.trim() || 'default',
      }
      if (model) body.model_name = model
      if (lu !== null) body.limit_usd = lu
      if (lt !== null) body.limit_tokens = lt
      if (lr !== null) body.limit_requests = lr
      applyPeriodResetToBody(body, values)
      applyValidityToBody(body, values)
      rules.push(body)
    }
  }
  return rules
}
