import { useEffect, useState } from 'react'

import type { QuotaRule } from '@/api/gateway/quota-rules'
import { PeriodResetFields } from '@/features/gateway-budget/period-reset-fields'
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
import { cn } from '@/lib/utils'

import { buildModelQuotaDefaultForm } from './model-detail-quota-utils'

function QuotaModelScopeCard({
  gatewayAlias,
  upstreamName,
  credentialLabel,
  layer,
}: {
  gatewayAlias: string
  upstreamName?: string | null
  credentialLabel?: string | null
  layer: 'platform' | 'upstream'
}): React.JSX.Element {
  const borderClass =
    layer === 'platform' ? 'border-sky-500/20' : 'border-amber-500/20 bg-background/80'
  return (
    <div className={cn('rounded-md border px-3 py-2 text-xs', borderClass)}>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="min-w-0">
          <p className="text-[10px] uppercase tracking-wide text-muted-foreground">调用名</p>
          <p className="mt-0.5 truncate font-medium text-foreground" title={gatewayAlias}>
            {gatewayAlias}
          </p>
        </div>
        {layer === 'upstream' && upstreamName ? (
          <div className="min-w-0">
            <p className="text-[10px] uppercase tracking-wide text-muted-foreground">上游模型</p>
            <p className="mt-0.5 truncate font-mono text-muted-foreground" title={upstreamName}>
              {upstreamName}
            </p>
          </div>
        ) : null}
      </div>
      {layer === 'upstream' && credentialLabel ? (
        <p className="mt-2 text-muted-foreground">
          凭据 <span className="text-foreground">{credentialLabel}</span>
        </p>
      ) : null}
      {layer === 'platform' ? (
        <p className="mt-2 text-muted-foreground">平台护栏按网关调用名计量，非上游 endpoint。</p>
      ) : null}
    </div>
  )
}

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
  gatewayAlias,
}: SharedFormProps & { memberLabel?: string; gatewayAlias: string }): React.JSX.Element {
  const { values, limitTokensWan, setLimitTokensWan, update, editingBudgetId, buildSubmitPayload } =
    useModelQuotaFormState(modelName, credentialId, 'platform', mode, selfUserId, editingRule)

  return (
    <QuotaFormShell
      icon={
        <div className="flex h-7 w-7 items-center justify-center rounded-md bg-sky-500/10 text-sky-700 dark:text-sky-300">
          <Shield className="h-3.5 w-3.5" />
        </div>
      }
      title={editingRule ? '编辑网关护栏' : '新建网关护栏'}
      pending={pending}
      deletePending={deletePending}
      editingBudgetId={editingBudgetId}
      isEditing={editingRule !== null}
      onCancel={onCancel}
      onDelete={onDelete}
      onSubmit={() => {
        onSubmit(buildSubmitPayload())
      }}
      borderClass="border-sky-500/25 bg-sky-500/[0.04]"
    >
      <QuotaModelScopeCard gatewayAlias={gatewayAlias} layer="platform" />
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
      <PeriodResetFields
        layer="platform"
        period={values.period}
        periodTimezone={values.periodTimezone}
        periodResetTime={values.periodResetTime}
        periodResetDay={values.periodResetDay}
        onPeriodTimezoneChange={(periodTimezone) => {
          update('periodTimezone', periodTimezone)
        }}
        onPeriodResetTimeChange={(periodResetTime) => {
          update('periodResetTime', periodResetTime)
        }}
        onPeriodResetDayChange={(periodResetDay) => {
          update('periodResetDay', periodResetDay)
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
  gatewayAlias,
}: SharedFormProps & {
  credentialLabel: string
  upstreamModelId: string
  gatewayAlias: string
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
      title={editingRule ? '编辑凭据额度' : '新建凭据额度'}
      pending={pending}
      deletePending={deletePending}
      editingBudgetId={editingBudgetId}
      isEditing={editingRule !== null}
      onCancel={onCancel}
      onDelete={onDelete}
      onSubmit={() => {
        onSubmit(buildSubmitPayload())
      }}
      borderClass="border-amber-500/30 bg-amber-500/[0.06]"
    >
      <QuotaModelScopeCard
        gatewayAlias={gatewayAlias}
        upstreamName={upstreamModelId}
        credentialLabel={credentialLabel}
        layer="upstream"
      />
      <QuotaWindowPresetFields
        windowSeconds={values.windowSeconds}
        onWindowSecondsChange={(v) => {
          update('windowSeconds', v)
        }}
      />
      <PeriodResetFields
        layer="upstream"
        windowSeconds={values.windowSeconds}
        periodTimezone={values.periodTimezone}
        periodResetTime={values.periodResetTime}
        periodResetDay={values.periodResetDay}
        onPeriodTimezoneChange={(periodTimezone) => {
          update('periodTimezone', periodTimezone)
        }}
        onPeriodResetTimeChange={(periodResetTime) => {
          update('periodResetTime', periodResetTime)
        }}
        onPeriodResetDayChange={(periodResetDay) => {
          update('periodResetDay', periodResetDay)
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
