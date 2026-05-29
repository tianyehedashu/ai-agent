/**
 * 单条团队/系统凭据表格行（供 flat 表与分组列表复用）。
 */

import type React from 'react'

import { Link } from 'react-router-dom'

import type { GatewayCredentialUpdateBody, ProviderCredential } from '@/api/gateway'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { isConfigManagedSystemCredential } from '@/features/gateway-credentials/config-managed-credential'
import { displayApiBaseForCredential } from '@/features/gateway-credentials/credential-api-bases-utils'
import {
  canEditGatewayCredential,
  canLinkToCredentialDetail,
  credentialDetailTeamId,
} from '@/features/gateway-credentials/credential-permissions'
import { RestrictedCredentialGrantHint } from '@/features/gateway-credentials/credential-restricted-grant-hint'
import {
  CredentialScopeBadge,
  CredentialTeamBadge,
  CredentialVisibilityBadge,
} from '@/features/gateway-credentials/credential-scope-display'
import {
  defaultApiBaseForProvider,
  providerLabel,
} from '@/features/gateway-credentials/provider-schemas'
import {
  credentialDetailAddModelsHref,
  credentialDetailHref,
} from '@/features/gateway-models/paths'
import { Trash2 } from '@/lib/lucide-icons'

export interface ManagedCredentialRowProps {
  credential: ProviderCredential
  routeTeamId: string
  listVariant: 'team' | 'system'
  showAffiliationColumn: boolean
  teamNameById: Map<string, string>
  viewerUserId: string | null | undefined
  canWrite: boolean
  isPlatformAdmin: boolean
  onDelete: (c: ProviderCredential) => void
  updateMutation: {
    isPending: boolean
    mutate: (args: {
      id: string
      body: GatewayCredentialUpdateBody
      credentialTeamId: string
    }) => void
  }
}

export function ManagedCredentialRow({
  credential: c,
  routeTeamId,
  listVariant,
  showAffiliationColumn,
  teamNameById,
  viewerUserId,
  canWrite,
  isPlatformAdmin,
  onDelete,
  updateMutation,
}: ManagedCredentialRowProps): React.JSX.Element {
  const editable = canEditGatewayCredential(c, viewerUserId, canWrite, isPlatformAdmin)
  const linkable = canLinkToCredentialDetail(c, viewerUserId, canWrite, isPlatformAdmin)
  const detailTeamId = credentialDetailTeamId(c, routeTeamId)
  const configManaged = isConfigManagedSystemCredential(c)
  const updateTeamId = c.tenant_id ?? routeTeamId
  const showAffiliation = showAffiliationColumn || listVariant === 'system'

  return (
    <tr className="border-b last:border-0 hover:bg-muted/20">
      <td className="px-4 py-2">
        <div className="flex flex-wrap items-center gap-2">
          {linkable ? (
            <Link
              to={credentialDetailHref(detailTeamId, c.id)}
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
      <td className="px-4 py-2">
        {editable ? (
          <Switch
            checked={c.is_active}
            disabled={updateMutation.isPending}
            onCheckedChange={(checked) => {
              updateMutation.mutate({
                id: c.id,
                body: { is_active: checked },
                credentialTeamId: updateTeamId,
              })
            }}
            aria-label={c.is_active ? '停用凭据' : '启用凭据'}
          />
        ) : (
          <span className="text-xs text-muted-foreground">{c.is_active ? '启用' : '禁用'}</span>
        )}
      </td>
      <td className="px-4 py-2">
        {editable || linkable ? (
          <div className="flex items-center gap-0.5">
            {linkable ? (
              <Button variant="ghost" size="sm" className="h-7 px-2 text-xs" asChild>
                <Link to={credentialDetailHref(detailTeamId, c.id)}>详情</Link>
              </Button>
            ) : null}
            {editable ? (
              <>
                <Button variant="ghost" size="sm" className="h-7 px-2 text-xs" asChild>
                  <Link to={credentialDetailAddModelsHref(detailTeamId, c.id)}>添加模型</Link>
                </Button>
                <Button
                  size="icon"
                  variant="ghost"
                  className="h-7 w-7 text-destructive hover:text-destructive"
                  disabled={updateMutation.isPending}
                  onClick={() => {
                    onDelete(c)
                  }}
                  aria-label="删除凭据"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </>
            ) : null}
          </div>
        ) : null}
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
