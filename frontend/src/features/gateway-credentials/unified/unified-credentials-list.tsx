/**
 * 统一凭据平铺表（个人 + 团队 + 系统，归属列）。
 */

import type React from 'react'

import type { GatewayCredentialUpdateBody, ProviderCredential } from '@/api/gateway'
import type { GatewayTeam } from '@/api/gateway/teams'
import { ScrollArea } from '@/components/ui/scroll-area'
import { CredentialSummaryTableRow } from '@/features/gateway-credentials/credential-summary-table-row'
import {
  listTabForCredential,
  listVariantForCredential,
  type UnifiedCredentialEntry,
} from '@/features/gateway-credentials/hooks/use-unified-credentials-list'
import { ManagedCredentialRow } from '@/features/gateway-credentials/managed-credential-row'
import { ManagedCredentialsTableHead } from '@/features/gateway-credentials/managed-credentials-table-head'
import { isGatewayTeamWritable } from '@/features/gateway-teams/gateway-team-write-policy'

export interface UnifiedCredentialsListProps {
  items: readonly UnifiedCredentialEntry[]
  filteredTotal: number
  hasActiveFilters: boolean
  routeTeamId: string
  teamById: ReadonlyMap<string, GatewayTeam>
  teamNameById: Map<string, string>
  viewerUserId: string | null
  isPlatformAdmin: boolean
  personalDeletePending: boolean
  updateMutation: {
    isPending: boolean
    mutate: (args: {
      id: string
      body: GatewayCredentialUpdateBody
      credentialTeamId: string
    }) => void
  }
  onEditPersonal: (credential: ProviderCredential) => void
  onAddModelsPersonal?: (credential: ProviderCredential) => void
  onDelete: (credential: ProviderCredential) => void
}

export function UnifiedCredentialsList({
  items,
  filteredTotal,
  hasActiveFilters,
  routeTeamId,
  teamById,
  teamNameById,
  viewerUserId,
  isPlatformAdmin,
  personalDeletePending,
  updateMutation,
  onEditPersonal,
  onAddModelsPersonal,
  onDelete,
}: UnifiedCredentialsListProps): React.JSX.Element {
  return (
    <ScrollArea className="w-full overscroll-y-contain">
      <table className="w-full min-w-[720px] text-sm">
        <ManagedCredentialsTableHead layout="compact" showAffiliationColumn />
        <tbody>
          {items.length > 0 ? (
            items.map((entry) => {
              if (entry.kind === 'summary') {
                return (
                  <CredentialSummaryTableRow
                    key={entry.summary.id}
                    summary={entry.summary}
                    teamNameById={teamNameById}
                  />
                )
              }

              const credential = entry.credential
              const listVariant = listVariantForCredential(credential)
              const team = credential.tenant_id ? teamById.get(credential.tenant_id) : undefined
              const canWrite =
                listVariant === 'personal'
                  ? true
                  : team
                    ? isGatewayTeamWritable(team, isPlatformAdmin)
                    : isPlatformAdmin

              return (
                <ManagedCredentialRow
                  key={`${credential.id}:${credential.tenant_id ?? 'user'}`}
                  credential={credential}
                  routeTeamId={routeTeamId}
                  listVariant={listVariant}
                  layout="compact"
                  showAffiliationColumn
                  teamNameById={teamNameById}
                  viewerUserId={viewerUserId}
                  canWrite={canWrite}
                  isPlatformAdmin={isPlatformAdmin}
                  listTab={listTabForCredential(credential)}
                  personalDeletePending={listVariant === 'personal' ? personalDeletePending : false}
                  onEdit={listVariant === 'personal' ? onEditPersonal : undefined}
                  onAddModels={listVariant === 'personal' ? onAddModelsPersonal : undefined}
                  onDelete={onDelete}
                  updateMutation={listVariant === 'personal' ? undefined : updateMutation}
                />
              )
            })
          ) : (
            <tr>
              <td colSpan={6} className="px-4 py-8 text-center text-sm text-muted-foreground">
                {hasActiveFilters && filteredTotal === 0
                  ? '无匹配的凭据，请调整筛选条件'
                  : '暂无凭据'}
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </ScrollArea>
  )
}
