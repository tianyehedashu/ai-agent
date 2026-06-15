import { useEffect, useState } from 'react'

import type { QuotaRule } from '@/api/gateway/quota-rules'
import type { QuotaBatchFormValues } from '@/features/gateway-budget/quota-batch-form'
import { quotaRuleToBatchFormValues } from '@/features/gateway-budget/quota-batch-from-rule'
import { QuotaFormShell } from '@/features/gateway-budget/quota-form-shell'
import {
  QuotaLimitValueFields,
  QuotaPlatformPeriodSelect,
  QuotaWindowPresetFields,
} from '@/features/gateway-budget/quota-limit-fields'
import {
  tokensToWanInput,
  wanInputToTokenString,
} from '@/features/gateway-budget/quota-token-display'
import { Cloud, Shield } from '@/lib/lucide-icons'

import { buildModelQuotaDefaultForm } from './model-detail-quota-utils'

interface SharedFormProps {
  modelName: string
  credentialId: string
  mode: 'admin' | 'member'
  selfUserId: string | null
  editingRule: QuotaRule | null
  pending: boolean
  deletePending: boolean
  onSubmit: (values: QuotaBatchFormValues) => void
  onDelete?: (budgetId: string) => void
  onCancel: () => void
}

function useModelQuotaFormState(
  modelName: string,
  credentialId: string,
  layer: 'platform' | 'upstream',
  mode: 'admin' | 'member',
  selfUserId: string | null,
  editingRule: QuotaRule | null,
  upstreamRealModel?: string
): {
  values: QuotaBatchFormValues
  limitTokensWan: string
  setLimitTokensWan: (value: string) => void
  update: <K extends keyof QuotaBatchFormValues>(key: K, value: QuotaBatchFormValues[K]) => void
  editingBudgetId: string | null
  buildSubmitPayload: () => QuotaBatchFormValues
} {
  const [values, setValues] = useState<QuotaBatchFormValues>(() =>
    buildModelQuotaDefaultForm({
      modelName,
      credentialId,
      layer,
      memberMode: mode === 'member',
      selfUserId,
      upstreamRealModel: layer === 'upstream' ? upstreamRealModel : undefined,
    })
  )
  const [limitTokensWan, setLimitTokensWan] = useState('')

  useEffect(() => {
    if (editingRule) {
      const parsed = quotaRuleToBatchFormValues(editingRule)
      const next =
        parsed?.values ??
        buildModelQuotaDefaultForm({
          modelName,
          credentialId,
          layer,
          memberMode: mode === 'member',
          selfUserId,
          upstreamRealModel: layer === 'upstream' ? upstreamRealModel : undefined,
        })
      setValues(next)
      setLimitTokensWan(tokensToWanInput(next.limit_tokens))
      return
    }
    const next = buildModelQuotaDefaultForm({
      modelName,
      credentialId,
      layer,
      memberMode: mode === 'member',
      selfUserId,
      upstreamRealModel: layer === 'upstream' ? upstreamRealModel : undefined,
    })
    setValues(next)
    setLimitTokensWan(tokensToWanInput(next.limit_tokens))
  }, [editingRule, modelName, credentialId, layer, mode, selfUserId, upstreamRealModel])

  const update = <K extends keyof QuotaBatchFormValues>(
    key: K,
    value: QuotaBatchFormValues[K]
  ): void => {
    setValues((current) => ({ ...current, [key]: value }))
  }

  const buildSubmitPayload = (): QuotaBatchFormValues => ({
    ...values,
    layer,
    limit_tokens: wanInputToTokenString(limitTokensWan),
    allModels: false,
    modelNames: [layer === 'upstream' && upstreamRealModel ? upstreamRealModel : modelName],
    allCredentials: false,
    credentialIds:
      layer === 'upstream' || (mode === 'member' && credentialId)
        ? [credentialId]
        : values.credentialIds,
    windowSeconds: values.windowSeconds.trim() || '0',
    quotaLabel: values.quotaLabel.trim() || 'default',
  })

  return {
    values,
    limitTokensWan,
    setLimitTokensWan,
    update,
    editingBudgetId: editingRule?.source_ref.budget_id ?? null,
    buildSubmitPayload,
  }
}

export function ModelDetailPlatformQuotaForm({
  modelName,
  credentialId,
  mode,
  selfUserId,
  editingRule,
  pending,
  deletePending,
  onSubmit,
  onDelete,
  onCancel,
  memberLabel,
}: SharedFormProps & { memberLabel?: string }): React.JSX.Element {
  const { values, limitTokensWan, setLimitTokensWan, update, editingBudgetId, buildSubmitPayload } =
    useModelQuotaFormState(modelName, credentialId, 'platform', mode, selfUserId, editingRule)

  return (
    <QuotaFormShell
      icon={
        <div className="flex h-7 w-7 items-center justify-center rounded-md bg-sky-500/10 text-sky-700 dark:text-sky-300">
          <Shield className="h-3.5 w-3.5" />
        </div>
      }
      title={editingBudgetId ? '编辑网关护栏' : '新建网关护栏'}
      pending={pending}
      deletePending={deletePending}
      editingBudgetId={editingBudgetId}
      onCancel={onCancel}
      onDelete={onDelete}
      onSubmit={() => {
        onSubmit(buildSubmitPayload())
      }}
      borderClass="border-sky-500/25 bg-sky-500/[0.04]"
    >
      <p className="text-xs text-muted-foreground">
        {mode === 'member' && memberLabel
          ? `限制 ${memberLabel} 通过本模型的网关调用，按自然日 / 月重置。`
          : '限制团队经本模型别名产生的网关用量，按自然日 / 月重置。'}
      </p>
      <QuotaPlatformPeriodSelect
        value={values.period}
        onChange={(period) => {
          update('period', period)
        }}
      />
      <QuotaLimitValueFields
        limitUsd={values.limit_usd}
        onLimitUsdChange={(v) => {
          update('limit_usd', v)
        }}
        tokenMode="wan"
        limitTokens={limitTokensWan}
        onLimitTokensChange={setLimitTokensWan}
      />
    </QuotaFormShell>
  )
}

export function ModelDetailUpstreamQuotaForm({
  modelName,
  credentialId,
  mode,
  selfUserId,
  editingRule,
  pending,
  deletePending,
  onSubmit,
  onDelete,
  onCancel,
  credentialLabel,
  upstreamModelId,
}: SharedFormProps & {
  credentialLabel: string
  upstreamModelId: string
}): React.JSX.Element {
  const { values, limitTokensWan, setLimitTokensWan, update, editingBudgetId, buildSubmitPayload } =
    useModelQuotaFormState(
      modelName,
      credentialId,
      'upstream',
      mode,
      selfUserId,
      editingRule,
      upstreamModelId
    )

  return (
    <QuotaFormShell
      icon={
        <div className="flex h-7 w-7 items-center justify-center rounded-md bg-amber-500/15 text-amber-700 dark:text-amber-300">
          <Cloud className="h-3.5 w-3.5" />
        </div>
      }
      title={editingBudgetId ? '编辑凭据额度' : '新建凭据额度'}
      pending={pending}
      deletePending={deletePending}
      editingBudgetId={editingBudgetId}
      onCancel={onCancel}
      onDelete={onDelete}
      onSubmit={() => {
        onSubmit(buildSubmitPayload())
      }}
      borderClass="border-amber-500/30 bg-amber-500/[0.06]"
    >
      <div className="rounded-md border border-amber-500/20 bg-background/80 px-3 py-2 text-xs">
        <p className="font-medium text-foreground">{credentialLabel}</p>
        <p className="mt-1 font-mono text-muted-foreground">upstream · {upstreamModelId}</p>
      </div>
      <QuotaWindowPresetFields
        windowSeconds={values.windowSeconds}
        onWindowSecondsChange={(v) => {
          update('windowSeconds', v)
        }}
      />
      <QuotaLimitValueFields
        limitUsd={values.limit_usd}
        onLimitUsdChange={(v) => {
          update('limit_usd', v)
        }}
        tokenMode="wan"
        limitTokens={limitTokensWan}
        onLimitTokensChange={setLimitTokensWan}
        usdLabel="厂商费用上限 (USD)"
        usdPlaceholder="例如 500"
      />
    </QuotaFormShell>
  )
}
