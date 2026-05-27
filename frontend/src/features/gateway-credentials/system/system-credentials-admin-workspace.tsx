/**
 * 平台管理员 · 系统凭据 Tab 管理面。
 */

import { useCallback } from 'react'
import type React from 'react'

import { useQuery } from '@tanstack/react-query'

import { credentialsApi } from '@/api/gateway/credentials'
import { Button } from '@/components/ui/button'
import { TabsContent } from '@/components/ui/tabs'
import { CredentialDeleteConfirmDialog } from '@/features/gateway-credentials/credential-delete-confirm-dialog'
import { useCredentialDeleteFlow } from '@/features/gateway-credentials/hooks/use-credential-delete-flow'
import type { GatewayCredentialMutations } from '@/features/gateway-credentials/hooks/use-gateway-credential-mutations'
import { ManagedCredentialsTable } from '@/features/gateway-credentials/managed-credentials-table'
import { systemCredentialsTabQueryKey } from '@/features/gateway-credentials/query-keys'
import { GatewayRefreshButton } from '@/features/gateway-shared/gateway-refresh-button'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useGatewayTeamId } from '@/hooks/use-gateway-team-id'
import { Plus } from '@/lib/lucide-icons'

export interface SystemCredentialsAdminWorkspaceProps {
  mutations: GatewayCredentialMutations
  onAdd: (provider?: string) => void
}

export function SystemCredentialsAdminWorkspace({
  mutations,
  onAdd,
}: SystemCredentialsAdminWorkspaceProps): React.JSX.Element {
  const teamId = useGatewayTeamId()
  const { isAdmin, isPlatformAdmin } = useGatewayPermission()
  const deleteFlow = useCredentialDeleteFlow(mutations, teamId)

  const {
    data: systemItems,
    isLoading: systemLoading,
    isFetching,
    refetch,
  } = useQuery({
    queryKey: systemCredentialsTabQueryKey(teamId),
    queryFn: () => credentialsApi.listCredentials(teamId),
  })

  const systemCredentials = (systemItems ?? []).filter((c) => c.scope === 'system')

  const handleAdd = useCallback(() => {
    onAdd()
  }, [onAdd])

  return (
    <TabsContent value="system" className="mt-4 space-y-3 focus-visible:outline-none">
      <div className="flex justify-end gap-2">
        <GatewayRefreshButton
          isFetching={isFetching}
          ariaLabel="刷新系统凭据"
          onRefresh={() => refetch()}
        />
        <Button size="sm" onClick={handleAdd}>
          <Plus className="mr-1.5 h-4 w-4" />
          新增
        </Button>
      </div>

      <ManagedCredentialsTable
        items={systemCredentials}
        isLoading={systemLoading}
        routeTeamId={teamId}
        showEmptyAddButton={false}
        showAffiliationColumn
        canWrite={false}
        isAdmin={isAdmin}
        isPlatformAdmin={isPlatformAdmin}
        listVariant="system"
        emptyHint="暂无系统凭据"
        onAdd={onAdd}
        onDelete={deleteFlow.handleDeleteCredential}
        updateMutation={mutations.updateMutation}
      />

      <CredentialDeleteConfirmDialog
        credential={deleteFlow.credentialPendingDelete}
        isPending={deleteFlow.isDeletePending}
        onOpenChange={deleteFlow.handleDeleteDialogOpenChange}
        onConfirm={deleteFlow.handleDeleteConfirm}
      />
    </TabsContent>
  )
}
