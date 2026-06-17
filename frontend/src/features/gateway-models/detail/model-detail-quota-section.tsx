import { useMemo, useState } from 'react'

import type { GatewayModel } from '@/api/gateway/models'
import type { QuotaRule } from '@/api/gateway/quota-rules'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { buildRealModelsByCredentialMap } from '@/features/gateway-budget/quota-batch-rules'
import { useQuotaBatchSubmit } from '@/features/gateway-budget/use-quota-batch-submit'
import { credentialSummaryLabel } from '@/features/gateway-credentials/credential-summary-display'
import { useGatewayCredentialDirectory } from '@/features/gateway-credentials/use-credential-directory'
import type { ModelInspectorScope } from '@/features/gateway-models/detail/model-inspector'
import { useModelDetailQuotaRules } from '@/features/gateway-models/detail/use-model-detail-quota-rules'
import { Loader2 } from '@/lib/lucide-icons'

import { ModelDetailQuotaLayerPanel } from './model-detail-quota-layer-panel'

interface ModelDetailQuotaSectionProps {
  model: GatewayModel
  scope: ModelInspectorScope
  teamId: string
  userId: string | null
  isAdmin: boolean
  canManageQuota: boolean
}

type ActiveLayer = 'platform' | 'upstream'

type FormMode =
  | { kind: 'closed' }
  | { kind: 'create'; layer: ActiveLayer }
  | { kind: 'edit'; layer: ActiveLayer; rule: QuotaRule }

function layerFormMode(
  formMode: FormMode,
  layer: ActiveLayer
): { kind: 'closed' } | { kind: 'create' } | { kind: 'edit'; rule: QuotaRule } {
  if (formMode.kind === 'closed' || formMode.layer !== layer) return { kind: 'closed' }
  if (formMode.kind === 'create') return { kind: 'create' }
  return { kind: 'edit', rule: formMode.rule }
}

export function ModelDetailQuotaSection({
  model,
  scope,
  teamId,
  userId,
  isAdmin,
  canManageQuota,
}: ModelDetailQuotaSectionProps): React.JSX.Element | null {
  const isPersonal = scope === 'personal'
  const modelName = isPersonal ? model.real_model : model.name
  const gatewayAliasName = isPersonal ? model.name.trim() || model.real_model : model.name
  const canWrite = Boolean(userId) && canManageQuota
  const mode = isAdmin ? 'admin' : 'member'

  const { byId: credentialSummariesById } = useGatewayCredentialDirectory()
  const credentialSummary = credentialSummariesById.get(model.credential_id)
  const credentialOwnerId = credentialSummary?.created_by_user_id ?? null
  const credentialLabel = credentialSummaryLabel(credentialSummary, model.credential_id)

  const { platformRules, upstreamRules, isLoading } = useModelDetailQuotaRules({
    model,
    scope,
    teamId,
    userId,
  })

  const [formMode, setFormMode] = useState<FormMode>({ kind: 'closed' })

  const upstreamBatchRuleOptions = useMemo(
    () => ({
      realModelsByCredential: buildRealModelsByCredentialMap({
        teamModels: isPersonal
          ? []
          : [{ credential_id: model.credential_id, real_model: model.real_model }],
        personalModels: isPersonal
          ? [{ credential_id: model.credential_id, model_id: model.real_model }]
          : [],
      }),
    }),
    [isPersonal, model.credential_id, model.real_model]
  )

  const { submitForm, deleteRule, batchPending, deletePending } = useQuotaBatchSubmit({
    teamId,
    mode,
    selfUserId: userId,
    buildBatchRulesOptions: upstreamBatchRuleOptions,
    onSuccess: () => {
      setFormMode({ kind: 'closed' })
    },
  })

  const handleDeleteFromRow = (rule: QuotaRule): void => {
    const budgetId = rule.source_ref.budget_id
    if (!budgetId) return
    if (!window.confirm('确定删除此限额？')) return
    deleteRule(budgetId)
  }

  if (!userId) return null

  const showUpstreamPanel =
    Boolean(model.credential_id) ||
    upstreamRules.length > 0 ||
    (formMode.kind !== 'closed' && formMode.layer === 'upstream')

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">用量限额</CardTitle>
        <p className="text-xs text-muted-foreground">
          两层独立管控：网关护栏管平台计费，凭据额度管厂商 API；互不替代。
          {!canWrite
            ? ' 仅团队管理员可改团队护栏；成员可设「我的护栏」或本人凭据上的厂商额度。'
            : null}
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        {isLoading ? (
          <div className="flex items-center gap-2 py-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            加载…
          </div>
        ) : null}

        <ModelDetailQuotaLayerPanel
          layer="platform"
          rules={platformRules}
          teamId={teamId}
          canWrite={canWrite}
          isAdmin={isAdmin}
          credentialOwnerId={credentialOwnerId}
          formMode={layerFormMode(formMode, 'platform')}
          onOpenCreate={() => {
            setFormMode({ kind: 'create', layer: 'platform' })
          }}
          onOpenEdit={(rule) => {
            setFormMode({ kind: 'edit', layer: 'platform', rule })
          }}
          onCloseForm={() => {
            setFormMode({ kind: 'closed' })
          }}
          onSubmit={submitForm}
          onDelete={deleteRule}
          onDeleteFromRow={handleDeleteFromRow}
          pending={batchPending}
          deletePending={deletePending}
          modelName={modelName}
          gatewayAliasName={gatewayAliasName}
          credentialId={model.credential_id}
          mode={mode}
          selfUserId={userId}
          memberLabel={mode === 'member' ? '你' : undefined}
        />

        {showUpstreamPanel ? (
          <ModelDetailQuotaLayerPanel
            layer="upstream"
            rules={upstreamRules}
            teamId={teamId}
            canWrite={canWrite}
            isAdmin={isAdmin}
            credentialOwnerId={credentialOwnerId}
            formMode={layerFormMode(formMode, 'upstream')}
            onOpenCreate={() => {
              setFormMode({ kind: 'create', layer: 'upstream' })
            }}
            onOpenEdit={(rule) => {
              setFormMode({ kind: 'edit', layer: 'upstream', rule })
            }}
            onCloseForm={() => {
              setFormMode({ kind: 'closed' })
            }}
            onSubmit={submitForm}
            onDelete={deleteRule}
            onDeleteFromRow={handleDeleteFromRow}
            pending={batchPending}
            deletePending={deletePending}
            modelName={modelName}
            gatewayAliasName={gatewayAliasName}
            credentialId={model.credential_id}
            credentialLabel={credentialLabel}
            upstreamModelId={model.real_model}
            mode={mode}
            selfUserId={userId}
            unavailableReason={
              !model.credential_id ? '本模型未绑定凭据，无法设置厂商额度。' : undefined
            }
          />
        ) : null}
      </CardContent>
    </Card>
  )
}
