/**
 * 团队 Tab：按协作团队分组的凭据管理（不含 personal team）。
 */

import { useCallback, useDeferredValue, useMemo, useState } from 'react'
import type React from 'react'

import { PaginationControls } from '@/components/pagination-controls'
import { Card, CardContent } from '@/components/ui/card'
import { TabsContent } from '@/components/ui/tabs'
import { CredentialDeleteConfirmDialog } from '@/features/gateway-credentials/credential-delete-confirm-dialog'
import { useCredentialDeleteFlow } from '@/features/gateway-credentials/hooks/use-credential-delete-flow'
import type { GatewayCredentialMutations } from '@/features/gateway-credentials/hooks/use-gateway-credential-mutations'
import { CollaborationTeamsCredentialsGroupedList } from '@/features/gateway-credentials/team/collaboration-teams-credentials-grouped-list'
import { CredentialsEmptyState } from '@/features/gateway-credentials/team/credentials-empty-state'
import {
  CredentialsWorkspaceToolbar,
  type CredentialsWorkspaceSummary,
} from '@/features/gateway-credentials/team/credentials-workspace-toolbar'
import { useManagedTeamCredentialsList } from '@/features/gateway-credentials/use-managed-team-credentials-list'
import { groupResourcesByTenantId } from '@/features/gateway-teams/resolve-collaboration-teams-candidates'
import { useCollaborationTeamsOverviewResolution } from '@/features/gateway-teams/use-collaboration-teams-overview-resolution'
import {
  useGatewayMemberCollaborationTeams,
  useGatewayWritableCollaborationTeams,
} from '@/features/gateway-teams/use-gateway-teams'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useGatewayTeamId } from '@/hooks/use-gateway-team-id'
import { useUserStore } from '@/stores/user'

export interface TeamCredentialsWorkspaceProps {
  mutations: GatewayCredentialMutations
  onAdd: (provider?: string, teamId?: string) => void
}

export function TeamCredentialsWorkspace({
  mutations,
  onAdd,
}: TeamCredentialsWorkspaceProps): React.JSX.Element {
  const routeTeamId = useGatewayTeamId()
  const memberCollaborationTeams = useGatewayMemberCollaborationTeams()
  const writableCollaborationTeams = useGatewayWritableCollaborationTeams()
  const viewerUserId = useUserStore((s) => s.currentUser?.id ?? null)
  const { isPlatformAdmin } = useGatewayPermission()
  const [teamSearch, setTeamSearch] = useState('')
  const deferredTeamSearch = useDeferredValue(teamSearch)
  const [page, setPage] = useState(1)

  const hasCollaborationTeams = memberCollaborationTeams.length > 0
  const teamSearchTrimmed = teamSearch.trim()
  const isListSearchStale = deferredTeamSearch.trim() !== teamSearchTrimmed

  const {
    data: listData,
    isLoading,
    isFetching,
    refetch,
  } = useManagedTeamCredentialsList({
    search: deferredTeamSearch,
    page,
    enabled: hasCollaborationTeams,
  })

  const deleteFlow = useCredentialDeleteFlow(mutations, routeTeamId)

  const {
    teams: displayTeams,
    requiresSearch,
    isSearchStale: isTeamsSearchStale,
  } = useCollaborationTeamsOverviewResolution({
    teamSearch,
    queriedTeamCount: listData?.queried_team_count,
    isPlatformAdmin,
    viewerUserId,
    enabled: hasCollaborationTeams,
  })

  const credentialsByTeamId = useMemo(
    () => groupResourcesByTenantId(listData?.items ?? []),
    [listData?.items]
  )

  const tenantIdsWithCredentials = useMemo(
    () => new Set(listData?.tenant_ids_with_credentials ?? []),
    [listData?.tenant_ids_with_credentials]
  )

  const defaultAddTeamId = displayTeams[0]?.id ?? writableCollaborationTeams[0]?.id

  const handleTeamSearchChange = useCallback((value: string) => {
    setTeamSearch(value)
    setPage(1)
  }, [])

  const handleAddForTeam = useCallback(
    (targetTeamId: string) => {
      onAdd(undefined, targetTeamId)
    },
    [onAdd]
  )

  const handleRefresh = useCallback(() => {
    void refetch()
  }, [refetch])

  const summary = useMemo((): CredentialsWorkspaceSummary | undefined => {
    if (!listData) return undefined
    return {
      total: listData.total,
      queriedTeamCount: listData.queried_team_count,
      queriedSharedTeamCount: listData.queried_shared_team_count,
      isPlatformAdmin,
    }
  }, [isPlatformAdmin, listData])

  const showLoading = isLoading || isListSearchStale || isTeamsSearchStale
  const showEmptyPanel =
    !showLoading &&
    !hasCollaborationTeams &&
    !requiresSearch &&
    (listData?.total ?? 0) === 0 &&
    displayTeams.length === 0

  const showSearchEmpty =
    !showLoading &&
    hasCollaborationTeams &&
    !requiresSearch &&
    displayTeams.length === 0 &&
    teamSearchTrimmed.length > 0

  const tableFooter =
    listData && listData.total > listData.page_size ? (
      <PaginationControls
        page={listData.page}
        page_size={listData.page_size}
        total={listData.total}
        has_next={listData.has_next}
        has_prev={listData.has_prev}
        onPageChange={setPage}
      />
    ) : null

  return (
    <TabsContent value="shared" className="mt-4 focus-visible:outline-none">
      <Card>
        {hasCollaborationTeams ? (
          <div className="border-b p-3">
            <CredentialsWorkspaceToolbar
              teamSearch={teamSearch}
              onTeamSearchChange={handleTeamSearchChange}
              summary={summary}
              canAdd={hasCollaborationTeams}
              isRefreshing={isFetching}
              onRefresh={handleRefresh}
              onAdd={() => {
                onAdd(undefined, defaultAddTeamId)
              }}
            />
          </div>
        ) : null}
        <CardContent className="p-0">
          {showEmptyPanel ? (
            <div className="p-4">
              <CredentialsEmptyState noCollaborationTeams />
            </div>
          ) : showSearchEmpty ? (
            <div className="p-4">
              <CredentialsEmptyState hasActiveSearch />
            </div>
          ) : (
            <CollaborationTeamsCredentialsGroupedList
              teams={displayTeams}
              credentialsByTeamId={credentialsByTeamId}
              tenantIdsWithCredentials={tenantIdsWithCredentials}
              requiresSearch={requiresSearch}
              isLoading={showLoading}
              currentPage={page}
              isPlatformAdmin={isPlatformAdmin}
              viewerUserId={viewerUserId}
              routeTeamId={routeTeamId}
              onAddForTeam={handleAddForTeam}
              onDelete={deleteFlow.handleDeleteCredential}
              updateMutation={mutations.updateMutation}
            />
          )}
        </CardContent>
        {tableFooter ? <div className="border-t px-3 py-2">{tableFooter}</div> : null}
      </Card>

      <CredentialDeleteConfirmDialog
        credential={deleteFlow.credentialPendingDelete}
        isPending={deleteFlow.isDeletePending}
        onOpenChange={deleteFlow.handleDeleteDialogOpenChange}
        onConfirm={deleteFlow.handleDeleteConfirm}
      />
    </TabsContent>
  )
}
