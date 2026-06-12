import { useEffect, useMemo, useState } from 'react'

import type { QuotaRule } from '@/api/gateway/quota-rules'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import type { QuotaBatchFormValues } from '@/features/gateway-budget/quota-batch-form'
import { quotaRuleToBatchFormValues } from '@/features/gateway-budget/quota-batch-from-rule'
import {
  tokensToWanInput,
  wanInputToTokenString,
} from '@/features/gateway-budget/quota-token-display'
import {
  applyQuotaWindowPreset,
  QUOTA_WINDOW_PRESETS,
  resolveQuotaWindowPreset,
  type QuotaWindowPresetValue,
} from '@/features/gateway-budget/quota-window-presets'
import { Cloud, Loader2, Shield, Trash2, X } from '@/lib/lucide-icons'

import { buildModelQuotaDefaultForm } from './model-detail-quota-utils'

interface QuotaFormShellProps {
  icon: React.ReactNode
  title: string
  pending: boolean
  deletePending: boolean
  editingBudgetId: string | null
  onCancel: () => void
  onDelete?: (budgetId: string) => void
  onSubmit: () => void
  children: React.ReactNode
  borderClass: string
}

function QuotaFormShell({
  icon,
  title,
  pending,
  deletePending,
  editingBudgetId,
  onCancel,
  onDelete,
  onSubmit,
  children,
  borderClass,
}: QuotaFormShellProps): React.JSX.Element {
  const isEditing = editingBudgetId !== null

  return (
    <div className={`space-y-3 rounded-md border p-3 ${borderClass}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          {icon}
          <p className="text-sm font-medium">{title}</p>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="h-7 w-7 shrink-0"
          onClick={onCancel}
        >
          <X className="h-3.5 w-3.5" />
        </Button>
      </div>
      {children}
      <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
        {isEditing && onDelete ? (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-7 text-xs text-destructive hover:text-destructive"
            disabled={deletePending || pending}
            onClick={() => {
              onDelete(editingBudgetId)
            }}
          >
            {deletePending ? (
              <Loader2 className="mr-1 h-3 w-3 animate-spin" />
            ) : (
              <Trash2 className="mr-1 h-3 w-3" />
            )}
            删除
          </Button>
        ) : (
          <span />
        )}
        <div className="flex gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-7 text-xs"
            onClick={onCancel}
          >
            取消
          </Button>
          <Button
            type="button"
            size="sm"
            className="h-7 text-xs"
            disabled={pending}
            onClick={onSubmit}
          >
            {pending ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : null}
            保存
          </Button>
        </div>
      </div>
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
  editingRule: QuotaRule | null
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
    })
    setValues(next)
    setLimitTokensWan(tokensToWanInput(next.limit_tokens))
  }, [editingRule, modelName, credentialId, layer, mode, selfUserId])

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
    modelNames: [modelName],
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
      <div className="space-y-1.5">
        <Label className="text-xs">重置周期</Label>
        <Select
          value={values.period}
          onValueChange={(v) => {
            update('period', v as QuotaBatchFormValues['period'])
          }}
        >
          <SelectTrigger className="h-8">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="daily">每日零点重置</SelectItem>
            <SelectItem value="monthly">每月 1 日重置</SelectItem>
            <SelectItem value="total">累计总量（不重置）</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className="space-y-1.5">
        <Label className="text-xs">费用上限 (USD)</Label>
        <Input
          className="h-9 text-base tabular-nums"
          inputMode="decimal"
          placeholder="例如 100"
          value={values.limit_usd}
          onChange={(e) => {
            update('limit_usd', e.target.value)
          }}
        />
      </div>
      <div className="space-y-1.5">
        <Label className="text-xs text-muted-foreground">或 Token 上限（万，可选）</Label>
        <Input
          className="h-8 tabular-nums"
          inputMode="decimal"
          placeholder="留空则不限 Token"
          value={limitTokensWan}
          onChange={(e) => {
            setLimitTokensWan(e.target.value)
          }}
        />
      </div>
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
    useModelQuotaFormState(modelName, credentialId, 'upstream', mode, selfUserId, editingRule)

  const windowPreset = useMemo(
    () => resolveQuotaWindowPreset(values.windowSeconds),
    [values.windowSeconds]
  )

  const handleWindowPresetChange = (preset: QuotaWindowPresetValue): void => {
    update('windowSeconds', applyQuotaWindowPreset(preset, values.windowSeconds))
  }

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
      <div className="space-y-1.5">
        <Label className="text-xs">统计窗口</Label>
        <Select value={windowPreset} onValueChange={handleWindowPresetChange}>
          <SelectTrigger className="h-8">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {QUOTA_WINDOW_PRESETS.map((preset) => (
              <SelectItem key={preset.value} value={preset.value}>
                {preset.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {windowPreset === 'custom' ? (
          <Input
            className="mt-2 h-8"
            inputMode="numeric"
            placeholder="自定义秒数，如 3600"
            value={values.windowSeconds}
            onChange={(e) => {
              update('windowSeconds', e.target.value)
            }}
          />
        ) : (
          <p className="text-[11px] text-muted-foreground">滚动窗口内累计，到期自动滑动清零。</p>
        )}
      </div>
      <div className="space-y-1.5">
        <Label className="text-xs">厂商费用上限 (USD)</Label>
        <Input
          className="h-9 text-base tabular-nums"
          inputMode="decimal"
          placeholder="例如 500"
          value={values.limit_usd}
          onChange={(e) => {
            update('limit_usd', e.target.value)
          }}
        />
      </div>
      <div className="space-y-1.5">
        <Label className="text-xs text-muted-foreground">或 Token 上限（万，可选）</Label>
        <Input
          className="h-8 tabular-nums"
          inputMode="decimal"
          placeholder="留空则不限 Token"
          value={limitTokensWan}
          onChange={(e) => {
            setLimitTokensWan(e.target.value)
          }}
        />
      </div>
    </QuotaFormShell>
  )
}
