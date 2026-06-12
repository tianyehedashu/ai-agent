import type { QuotaRuleUpsertBody } from '@/api/gateway'

import { parseOptionalInt, parseOptionalUsd } from './budget-form-utils'

import type { QuotaBatchFormValues } from './quota-batch-form'

/** 将批量表单展开为 upsert 规则列表；至少一项限额且主体/模型有效。 */
export function buildBatchRules(values: QuotaBatchFormValues): QuotaRuleUpsertBody[] | null {
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
    for (const credId of credentialTargets) {
      for (const model of models) {
        const body: QuotaRuleUpsertBody = {
          layer: 'upstream',
          window_seconds: ws,
          quota_label: values.quotaLabel.trim() || 'default',
        }
        if (credId) body.credential_id = credId
        if (model) body.model_name = model
        if (lu !== null) body.limit_usd = lu
        if (lt !== null) body.limit_tokens = lt
        if (lr !== null) body.limit_requests = lr
        rules.push(body)
      }
    }
    return rules
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
      rules.push(body)
    }
  }
  return rules
}
