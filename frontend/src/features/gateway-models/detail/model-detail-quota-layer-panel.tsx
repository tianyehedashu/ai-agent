import type { QuotaRule } from '@/api/gateway/quota-rules'
import { Button } from '@/components/ui/button'
import type { QuotaBatchFormValues } from '@/features/gateway-budget/quota-batch-form'
import { quotaRuleRowId } from '@/features/gateway-budget/quota-rule-utils'
import { Cloud, Pencil, Plus, Shield, Trash2 } from '@/lib/lucide-icons'
import { cn } from '@/lib/utils'

import {
  ModelDetailPlatformQuotaForm,
  ModelDetailUpstreamQuotaForm,
} from './model-detail-quota-forms'
import { ModelDetailQuotaRuleRow } from './model-detail-quota-rule-row'
import { isModelDetailEditableQuotaRule } from './model-detail-quota-utils'

type LayerFormMode = { kind: 'closed' } | { kind: 'create' } | { kind: 'edit'; rule: QuotaRule }

interface ModelDetailQuotaLayerPanelProps {
  layer: 'platform' | 'upstream'
  rules: QuotaRule[]
  canWrite: boolean
  formMode: LayerFormMode
  onOpenCreate: () => void
  onOpenEdit: (rule: QuotaRule) => void
  onCloseForm: () => void
  onSubmit: (values: QuotaBatchFormValues) => void
  onDelete: (budgetId: string) => void
  onDeleteFromRow: (rule: QuotaRule) => void
  pending: boolean
  deletePending: boolean
  modelName: string
  credentialId: string
  credentialLabel?: string
  upstreamModelId?: string
  mode: 'admin' | 'member'
  selfUserId: string
  memberLabel?: string
  unavailableReason?: string
}

const PANEL_META = {
  platform: {
    title: '网关消费护栏',
    subtitle: '管「经网关调用本模型」的团队 / 个人用量',
    accent: 'border-sky-500/20 bg-sky-500/[0.03]',
    iconWrap: 'bg-sky-500/10 text-sky-700 dark:text-sky-300',
    addLabel: '设护栏',
    emptyLabel: '尚未设置网关护栏',
  },
  upstream: {
    title: '厂商凭据额度',
    subtitle: '管「凭据直连厂商 API」的实际调用量',
    accent: 'border-amber-500/20 bg-amber-500/[0.03]',
    iconWrap: 'bg-amber-500/15 text-amber-700 dark:text-amber-300',
    addLabel: '设额度',
    emptyLabel: '尚未设置凭据额度',
  },
} as const

export function ModelDetailQuotaLayerPanel({
  layer,
  rules,
  canWrite,
  formMode,
  onOpenCreate,
  onOpenEdit,
  onCloseForm,
  onSubmit,
  onDelete,
  onDeleteFromRow,
  pending,
  deletePending,
  modelName,
  credentialId,
  credentialLabel,
  upstreamModelId,
  mode,
  selfUserId,
  memberLabel,
  unavailableReason,
}: ModelDetailQuotaLayerPanelProps): React.JSX.Element {
  const meta = PANEL_META[layer]
  const showForm = formMode.kind !== 'closed'
  const editingRule = formMode.kind === 'edit' ? formMode.rule : null
  const disabled = Boolean(unavailableReason)
  const panelIcon =
    layer === 'platform' ? <Shield className="h-4 w-4" /> : <Cloud className="h-4 w-4" />

  return (
    <section className={cn('space-y-3 rounded-lg border p-3', meta.accent)}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="flex min-w-0 items-start gap-2.5">
          <div
            className={cn(
              'flex h-8 w-8 shrink-0 items-center justify-center rounded-lg',
              meta.iconWrap
            )}
          >
            {panelIcon}
          </div>
          <div className="min-w-0">
            <h4 className="text-sm font-semibold">{meta.title}</h4>
            <p className="mt-0.5 text-xs text-muted-foreground">{meta.subtitle}</p>
          </div>
        </div>
        {canWrite && !showForm && !disabled ? (
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="h-7 text-xs"
            onClick={onOpenCreate}
          >
            <Plus className="mr-1 h-3 w-3" />
            {mode === 'member' && layer === 'platform' ? '设我的护栏' : meta.addLabel}
          </Button>
        ) : null}
      </div>

      {disabled ? <p className="text-xs text-muted-foreground">{unavailableReason}</p> : null}

      {showForm && !disabled ? (
        layer === 'platform' ? (
          <ModelDetailPlatformQuotaForm
            modelName={modelName}
            credentialId={credentialId}
            mode={mode}
            selfUserId={selfUserId}
            editingRule={editingRule}
            pending={pending}
            deletePending={deletePending}
            onSubmit={onSubmit}
            onDelete={onDelete}
            onCancel={onCloseForm}
            memberLabel={memberLabel}
          />
        ) : (
          <ModelDetailUpstreamQuotaForm
            modelName={modelName}
            credentialId={credentialId}
            mode={mode}
            selfUserId={selfUserId}
            editingRule={editingRule}
            pending={pending}
            deletePending={deletePending}
            onSubmit={onSubmit}
            onDelete={onDelete}
            onCancel={onCloseForm}
            credentialLabel={credentialLabel ?? '当前凭据'}
            upstreamModelId={upstreamModelId ?? modelName}
          />
        )
      ) : null}

      {!disabled && rules.length === 0 && !showForm ? (
        <p className="text-xs text-muted-foreground">{meta.emptyLabel}</p>
      ) : null}

      {rules.map((rule) => {
        const isEditingThis =
          formMode.kind === 'edit' && quotaRuleRowId(formMode.rule) === quotaRuleRowId(rule)
        if (isEditingThis) return null
        const editable = canWrite && isModelDetailEditableQuotaRule(rule)
        return (
          <ModelDetailQuotaRuleRow
            key={quotaRuleRowId(rule)}
            rule={rule}
            layer={layer}
            credentialLabel={credentialLabel}
            upstreamModelId={upstreamModelId}
            actions={
              editable && !showForm ? (
                <span className="inline-flex gap-1">
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    className="h-6 px-2 text-xs"
                    onClick={() => {
                      onOpenEdit(rule)
                    }}
                  >
                    <Pencil className="mr-0.5 h-3 w-3" />
                    编辑
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    className="h-6 px-2 text-xs text-destructive hover:text-destructive"
                    disabled={deletePending}
                    onClick={() => {
                      onDeleteFromRow(rule)
                    }}
                  >
                    <Trash2 className="mr-0.5 h-3 w-3" />
                    删除
                  </Button>
                </span>
              ) : null
            }
          />
        )
      })}
    </section>
  )
}

export type { LayerFormMode }
