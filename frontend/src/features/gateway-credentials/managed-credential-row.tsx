/**
 * 单条团队/系统凭据表格行（供 flat 表与分组列表复用）。
 */

import type React from 'react'

import { Link } from 'react-router-dom'

import type { GatewayCredentialUpdateBody, ProviderCredential } from '@/api/gateway'
import { Badge } from '@/components/ui/badge'
import { Switch } from '@/components/ui/switch'
import { CredentialAffiliationCell } from '@/features/gateway-credentials/components/credential-affiliation-cell'
import { isConfigManagedSystemCredential } from '@/features/gateway-credentials/config-managed-credential'
import { displayApiBaseForCredential } from '@/features/gateway-credentials/credential-api-bases-utils'
import {
  canEditGatewayCredential,
  canLinkToCredentialDetail,
  credentialDetailTeamId,
} from '@/features/gateway-credentials/credential-permissions'
import { RestrictedCredentialGrantHint } from '@/features/gateway-credentials/credential-restricted-grant-hint'
import { CredentialRowActions } from '@/features/gateway-credentials/credential-row-actions'
import {
  CredentialScopeBadge,
  CredentialTeamBadge,
  CredentialVisibilityBadge,
} from '@/features/gateway-credentials/credential-scope-display'
import { useCredentialActiveToggle } from '@/features/gateway-credentials/hooks/use-credential-active-toggle'
import type { ManagedCredentialsTableLayout } from '@/features/gateway-credentials/managed-credentials-table-head'
import {
  defaultApiBaseForProvider,
  providerLabel,
} from '@/features/gateway-credentials/provider-schemas'
import type { CredentialsListTab } from '@/features/gateway-models/paths'
import { credentialDetailHref } from '@/features/gateway-models/paths'

export interface ManagedCredentialRowProps {
  credential: ProviderCredential
  routeTeamId: string
  listVariant: 'team' | 'system' | 'personal'
  layout?: ManagedCredentialsTableLayout
  showAffiliationColumn: boolean
  teamNameById: Map<string, string>
  viewerUserId: string | null | undefined
  canWrite: boolean
  isPlatformAdmin: boolean
  listTab?: CredentialsListTab
  onDelete: (c: ProviderCredential) => void
  updateMutation?: {
    isPending: boolean
    mutate: (args: {
      id: string
      body: GatewayCredentialUpdateBody
      credentialTeamId: string
    }) => void
  }
  onEdit?: (credential: ProviderCredential) => void
  onAddModels?: (credential: ProviderCredential) => void
  personalDeletePending?: boolean
}

export function ManagedCredentialRow({
  credential: c,
  routeTeamId,
  listVariant,
  layout = 'full',
  showAffiliationColumn,
  teamNameById,
  viewerUserId,
  canWrite,
  isPlatformAdmin,
  listTab,
  onDelete,
  updateMutation,
  onEdit,
  onAddModels,
  personalDeletePending = false,
}: ManagedCredentialRowProps): React.JSX.Element {
  const isPersonal = listVariant === 'personal'
  const editable = isPersonal
    ? true
    : canEditGatewayCredential(c, viewerUserId, canWrite, isPlatformAdmin)
  const linkable = isPersonal
    ? false
    : canLinkToCredentialDetail(c, viewerUserId, canWrite, isPlatformAdmin)
  const detailTeamId = credentialDetailTeamId(c, routeTeamId)
  const configManaged = isConfigManagedSystemCredential(c)
  const showAffiliation = showAffiliationColumn || listVariant === 'system'
  const linkState = listTab ? { credentialsTab: listTab } : undefined
  const activeToggle = useCredentialActiveToggle({
    credential: c,
    routeTeamId,
    scope: isPersonal ? 'user' : c.scope === 'system' ? 'system' : 'team',
  })
  const deletePending = isPersonal ? personalDeletePending : (updateMutation?.isPending ?? false)

  const activeCell =
    editable && layout === 'compact' ? (
      <Switch
        checked={c.is_active}
        disabled={activeToggle.isPending || deletePending}
        onCheckedChange={(checked) => {
          activeToggle.toggle(checked)
        }}
        aria-label={c.is_active ? '停用凭据' : '启用凭据'}
      />
    ) : editable && updateMutation ? (
      <Switch
        checked={c.is_active}
        disabled={updateMutation.isPending}
        onCheckedChange={(checked) => {
          updateMutation.mutate({
            id: c.id,
            body: { is_active: checked },
            credentialTeamId: c.tenant_id ?? routeTeamId,
          })
        }}
        aria-label={c.is_active ? '停用凭据' : '启用凭据'}
      />
    ) : (
      <Badge variant={c.is_active ? 'secondary' : 'outline'} className="text-[10px] font-normal">
        {c.is_active ? '启用' : '停用'}
      </Badge>
    )

  if (layout === 'compact') {
    return (
      <tr className="border-b last:border-0 hover:bg-muted/20" data-credential-id={c.id}>
        <td className="px-4 py-2">
          <div className="flex flex-wrap items-center gap-2">
            {linkable ? (
              <Link
                to={credentialDetailHref(detailTeamId, c.id, { tab: listTab })}
                state={linkState}
                className="font-medium text-primary underline-offset-4 hover:underline"
              >
                {c.name}
              </Link>
            ) : onEdit ? (
              <button
                type="button"
                className="font-medium text-primary underline-offset-4 hover:underline"
                onClick={() => {
                  onEdit(c)
                }}
              >
                {c.name}
              </button>
            ) : (
              <span className="font-medium">{c.name}</span>
            )}
            {!isPersonal && c.management_access === 'metadata' ? (
              <Badge variant="outline" className="text-[10px] font-normal">
                只读
              </Badge>
            ) : null}
            {configManaged ? (
              <Badge variant="secondary" className="text-[10px] font-normal">
                配置同步
              </Badge>
            ) : null}
            {isPersonal && !c.is_active ? (
              <Badge variant="outline" className="text-[10px] font-normal">
                已停用
              </Badge>
            ) : null}
          </div>
        </td>
        <td className="px-4 py-2 font-mono text-xs text-muted-foreground">{c.api_key_masked}</td>
        <td className="px-4 py-2 text-xs">
          <div className="flex flex-col">
            <span className="font-medium">{providerLabel(c.provider)}</span>
            <span className="font-mono text-[10px] text-muted-foreground" title={c.provider}>
              {c.provider}
            </span>
          </div>
        </td>
        {showAffiliation ? (
          <td className="px-4 py-2">
            <CredentialAffiliationCell
              scope={c.scope}
              tenantId={c.tenant_id}
              visibility={c.visibility}
              teamNameById={teamNameById}
              compact
            />
          </td>
        ) : null}
        <td className="px-4 py-2">{activeCell}</td>
        <td className="px-4 py-2">
          <CredentialRowActions
            credential={c}
            detailTeamId={detailTeamId}
            listTab={listTab}
            linkable={linkable}
            editable={editable}
            deletePending={deletePending}
            onEdit={onEdit}
            onAddModels={onAddModels}
            onDelete={onDelete}
          />
        </td>
      </tr>
    )
  }

  return (
    <tr className="border-b last:border-0 hover:bg-muted/20" data-credential-id={c.id}>
      <td className="px-4 py-2">
        <div className="flex flex-wrap items-center gap-2">
          {linkable ? (
            <Link
              to={credentialDetailHref(detailTeamId, c.id, { tab: listTab })}
              state={linkState}
              className="font-medium text-primary underline-offset-4 hover:underline"
            >
              {c.name}
            </Link>
          ) : (
            <span className="font-medium">{c.name}</span>
          )}
          {c.management_access === 'metadata' ? (
            <Badge variant="outline" className="text-[10px] font-normal">
              只读
            </Badge>
          ) : null}
          {configManaged ? (
            <Badge variant="secondary" className="text-[10px] font-normal">
              配置同步
            </Badge>
          ) : null}
        </div>
      </td>
      <td className="px-4 py-2 font-mono text-xs text-muted-foreground">{c.api_key_masked}</td>
      <td className="px-4 py-2 text-xs">
        <div className="flex flex-col">
          <span className="font-medium">{providerLabel(c.provider)}</span>
          <span className="font-mono text-[10px] text-muted-foreground" title={c.provider}>
            {c.provider}
          </span>
        </div>
      </td>
      <td className="px-4 py-2">
        <CredentialScopeBadge scope={c.scope} />
      </td>
      {showAffiliation ? (
        <td className="px-4 py-2">
          {c.scope === 'team' ? (
            <CredentialTeamBadge tenantId={c.tenant_id} teamNameById={teamNameById} />
          ) : listVariant === 'system' ? (
            <div className="flex flex-col gap-0.5">
              <CredentialVisibilityBadge visibility={c.visibility} />
              {c.visibility === 'restricted' ? (
                <RestrictedCredentialGrantHint credentialId={c.id} />
              ) : null}
            </div>
          ) : (
            <span className="text-xs text-muted-foreground">—</span>
          )}
        </td>
      ) : null}
      <td className="px-4 py-2 text-xs">
        <CredentialApiBaseCell credential={c} />
      </td>
      <td className="px-4 py-2">{activeCell}</td>
      <td className="px-4 py-2">
        <CredentialRowActions
          credential={c}
          detailTeamId={detailTeamId}
          listTab={listTab}
          linkable={linkable}
          editable={editable}
          deletePending={deletePending}
          onEdit={onEdit}
          onAddModels={onAddModels}
          onDelete={onDelete}
        />
      </td>
    </tr>
  )
}

function CredentialApiBaseCell({
  credential,
}: Readonly<{ credential: ProviderCredential }>): React.JSX.Element {
  const base = displayApiBaseForCredential(credential)
  if (!base) return <span className="text-muted-foreground">—</span>
  const defaultBase = defaultApiBaseForProvider(credential.provider)
  const isDefault = Boolean(defaultBase) && base === defaultBase
  const keys = credential.extra ? Object.keys(credential.extra) : []
  return (
    <div className="flex flex-col gap-0.5">
      <div className="flex flex-wrap items-center gap-1">
        <span className="break-all">{base}</span>
        {isDefault ? (
          <Badge variant="outline" className="px-1 py-0 text-[10px]">
            默认
          </Badge>
        ) : null}
      </div>
      {keys.length > 0 ? (
        <span className="font-mono text-[10px] text-muted-foreground">
          extra: {keys.join(', ')}
        </span>
      ) : null}
    </div>
  )
}
