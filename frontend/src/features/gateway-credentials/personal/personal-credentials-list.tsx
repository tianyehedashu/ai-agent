/**
 * 个人凭据平铺表：与团队 Tab 凭据行一致，无提供商分组标头。
 */

import type React from 'react'

import type { ProviderCredential } from '@/api/gateway'
import { ScrollArea } from '@/components/ui/scroll-area'
import { ManagedCredentialRow } from '@/features/gateway-credentials/managed-credential-row'
import { ManagedCredentialsTableHead } from '@/features/gateway-credentials/managed-credentials-table-head'

export interface PersonalCredentialsListProps {
  credentials: readonly ProviderCredential[]
  routeTeamId: string
  deletePending: boolean
  onEdit: (credential: ProviderCredential) => void
  onAddModels?: (credential: ProviderCredential) => void
  onDelete: (credential: ProviderCredential) => void
}

export function PersonalCredentialsList({
  credentials,
  routeTeamId,
  deletePending,
  onEdit,
  onAddModels,
  onDelete,
}: PersonalCredentialsListProps): React.JSX.Element {
  return (
    <ScrollArea className="w-full overscroll-y-contain">
      <table className="w-full min-w-[640px] text-sm">
        <ManagedCredentialsTableHead layout="compact" listVariant="team" />
        <tbody>
          {credentials.length > 0 ? (
            credentials.map((credential) => (
              <ManagedCredentialRow
                key={credential.id}
                credential={credential}
                routeTeamId={routeTeamId}
                listVariant="personal"
                layout="compact"
                showAffiliationColumn={false}
                teamNameById={new Map()}
                viewerUserId={null}
                canWrite
                isPlatformAdmin={false}
                listTab="personal"
                personalDeletePending={deletePending}
                onEdit={onEdit}
                onAddModels={onAddModels}
                onDelete={onDelete}
              />
            ))
          ) : (
            <tr>
              <td colSpan={5} className="px-4 py-8 text-center text-sm text-muted-foreground">
                暂无凭据
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </ScrollArea>
  )
}
