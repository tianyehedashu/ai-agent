/**
 * 平台管理员 · 系统凭据 Tab 管理面。
 */

import { useCallback, useMemo } from 'react'
import type React from 'react'

import { useQuery } from '@tanstack/react-query'

import { credentialsApi } from '@/api/gateway/credentials'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { TabsContent } from '@/components/ui/tabs'
import { GatewayCredentialsListShell } from '@/features/gateway-credentials/components/gateway-credentials-list-shell'
import { CredentialDeleteConfirmDialog } from '@/features/gateway-credentials/credential-delete-confirm-dialog'
import { useCredentialDeleteFlow } from '@/features/gateway-credentials/hooks/use-credential-delete-flow'
import type { GatewayCredentialMutations } from '@/features/gateway-credentials/hooks/use-gateway-credential-mutations'
import { ManagedCredentialsTable } from '@/features/gateway-credentials/managed-credentials-table'
import { systemCredentialsTabQueryKey } from '@/features/gateway-credentials/query-keys'
import { GatewayRefreshButton } from '@/features/gateway-shared/gateway-refresh-button'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useGatewayTeamId } from '@/hooks/use-gateway-team-id'
import { Plus } from '@/lib/lucide-icons'
import { useCurrentUser } from '@/stores/user'

export interface SystemCredentialsAdminWorkspaceProps {
  mutations: GatewayCredentialMutations
  onAdd: (provider?: string) => void
  highlightCredentialId?: string
  hint?: string
}

export function SystemCredentialsAdminWorkspace({
  mutations,
  onAdd,
  hint,
}: SystemCredentialsAdminWorkspaceProps): React.JSX.Element {
  const teamId = useGatewayTeamId()
  const viewerUserId = useCurrentUser()?.id ?? null
  const { isPlatformAdmin } = useGatewayPermission()
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

  const systemCredentials = useMemo(
    () => (systemItems ?? []).filter((c) => c.scope === 'system'),
    [systemItems]
  )

  const handleAdd = useCallback(() => {
    onAdd()
  }, [onAdd])

  const toolbar = (
    <div className="flex flex-wrap items-center gap-2 sm:gap-3">
      <Badge variant="secondary" className="font-normal">
        {systemCredentials.length} 条系统凭据
      </Badge>
      <div className="ml-auto flex flex-wrap items-center gap-2">
        <GatewayRefreshButton
          isFetching={isFetching}
          ariaLabel="刷新系统凭据"
          onRefresh={() => {
            void refetch()
          }}
        />
        <Button size="sm" onClick={handleAdd}>
          <Plus className="mr-1.5 h-4 w-4" />
          新增
        </Button>
      </div>
    </div>
  )

  return (
    <TabsContent value="system" className="mt-4 focus-visible:outline-none">
      <GatewayCredentialsListShell
        hintSlot={hint}
        toolbar={toolbar}
        isLoading={systemLoading}
        isEmpty={!systemLoading && systemCredentials.length === 0}
      >
        <ManagedCredentialsTable
          items={systemCredentials}
          isLoading={systemLoading}
          routeTeamId={teamId}
          showEmptyAddButton={false}
          showAffiliationColumn
          viewerUserId={viewerUserId}
          canWrite={false}
          isPlatformAdmin={isPlatformAdmin}
          listVariant="system"
          listTab="system"
          emptyHint="暂无系统凭据"
          embedded
          onAdd={onAdd}
          onDelete={deleteFlow.handleDeleteCredential}
          updateMutation={mutations.updateMutation}
        />
      </GatewayCredentialsListShell>

      <CredentialDeleteConfirmDialog
        credential={deleteFlow.credentialPendingDelete}
        isPending={deleteFlow.isDeletePending}
        onOpenChange={deleteFlow.handleDeleteDialogOpenChange}
        onConfirm={deleteFlow.handleDeleteConfirm}
      />
    </TabsContent>
  )
}
