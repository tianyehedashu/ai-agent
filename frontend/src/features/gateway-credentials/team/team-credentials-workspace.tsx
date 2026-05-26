/**
 * 团队 Tab：当前团队 + 跨团队汇总凭据管理。
 */

import { useCallback, useDeferredValue, useState } from 'react'
import type React from 'react'

import { useQuery } from '@tanstack/react-query'

import { credentialsApi } from '@/api/gateway/credentials'
import { PaginationControls } from '@/components/pagination-controls'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { TabsContent } from '@/components/ui/tabs'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { CredentialDeleteConfirmDialog } from '@/features/gateway-credentials/credential-delete-confirm-dialog'
import {
  canViewCrossTeamCredentialsOverview,
  shouldShowTeamAffiliationColumn,
} from '@/features/gateway-credentials/credential-permissions'
import { useCredentialDeleteFlow } from '@/features/gateway-credentials/hooks/use-credential-delete-flow'
import type { GatewayCredentialMutations } from '@/features/gateway-credentials/hooks/use-gateway-credential-mutations'
import { ManagedCredentialsTable } from '@/features/gateway-credentials/managed-credentials-table'
import { teamCredentialsListQueryKey } from '@/features/gateway-credentials/query-keys'
import { useManagedTeamCredentialsList } from '@/features/gateway-credentials/use-managed-team-credentials-list'
import { gatewayCrossTeamOverviewTabLabel } from '@/features/gateway-teams/gateway-team-display'
import {
  resolveGatewayTeamLabel,
  useGatewayTeamNameMap,
  useGatewayWritableTeams,
} from '@/features/gateway-teams/use-gateway-teams'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useGatewayTeamId } from '@/hooks/use-gateway-team-id'
import { Plus } from '@/lib/lucide-icons'

type TeamCredentialsView = 'current-team' | 'cross-team'

export interface TeamCredentialsWorkspaceProps {
  mutations: GatewayCredentialMutations
  onAdd: (provider?: string) => void
}

export function TeamCredentialsWorkspace({
  mutations,
  onAdd,
}: TeamCredentialsWorkspaceProps): React.JSX.Element {
  const teamId = useGatewayTeamId()
  const teamNameById = useGatewayTeamNameMap()
  const currentTeamLabel = resolveGatewayTeamLabel(teamNameById, teamId)
  const writableTeams = useGatewayWritableTeams()
  const { canWrite, isPlatformAdmin, isAdmin } = useGatewayPermission()
  const crossTeamTabLabel = gatewayCrossTeamOverviewTabLabel(writableTeams.length, isPlatformAdmin)
  const [teamView, setTeamView] = useState<TeamCredentialsView>('current-team')
  const [crossTeamSearch, setCrossTeamSearch] = useState('')
  const deferredCrossTeamSearch = useDeferredValue(crossTeamSearch)
  const [crossTeamPage, setCrossTeamPage] = useState(1)

  const deleteFlow = useCredentialDeleteFlow(mutations, teamId)

  const showCrossTeamOverview = canViewCrossTeamCredentialsOverview(canWrite, writableTeams.length)
  const isCrossTeamView = teamView === 'cross-team'
  const crossTeamSearchTrimmed = crossTeamSearch.trim()
  const isCrossTeamSearchStale = deferredCrossTeamSearch.trim() !== crossTeamSearchTrimmed

  const { data: items, isLoading } = useQuery({
    queryKey: teamCredentialsListQueryKey(teamId),
    queryFn: () => credentialsApi.listCredentials(teamId),
    enabled: !isCrossTeamView,
  })

  const { data: crossTeamData, isLoading: crossTeamLoading } = useManagedTeamCredentialsList({
    search: deferredCrossTeamSearch,
    page: crossTeamPage,
    enabled: isCrossTeamView,
  })

  const teamCredentials = (items ?? []).filter((c) => c.scope !== 'system')
  const sharedTableItems = isCrossTeamView ? (crossTeamData?.items ?? []) : teamCredentials
  const sharedTableLoading = isCrossTeamView
    ? crossTeamLoading || isCrossTeamSearchStale
    : isLoading

  const affiliationColumn = shouldShowTeamAffiliationColumn(
    isCrossTeamView ? 'cross-team' : 'current-team',
    writableTeams.length
  )

  const handleCrossTeamSearchChange = useCallback((value: string) => {
    setCrossTeamSearch(value)
    setCrossTeamPage(1)
  }, [])

  const handleSelectCurrentTeam = useCallback(() => {
    setTeamView('current-team')
  }, [])

  const handleSelectCrossTeam = useCallback(() => {
    setTeamView('cross-team')
  }, [])

  const handleImport = useCallback(() => {
    mutations.importMutation.mutate()
  }, [mutations.importMutation])

  return (
    <TabsContent value="shared" className="mt-4 space-y-3 focus-visible:outline-none">
      {showCrossTeamOverview ? (
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div className="inline-flex rounded-md border p-0.5">
            <Button
              type="button"
              size="sm"
              variant={isCrossTeamView ? 'ghost' : 'secondary'}
              className="h-8 max-w-[180px]"
              title={currentTeamLabel}
              onClick={handleSelectCurrentTeam}
            >
              <span className="truncate">{currentTeamLabel}</span>
            </Button>
            <Button
              type="button"
              size="sm"
              variant={isCrossTeamView ? 'secondary' : 'ghost'}
              className="h-8"
              title={
                isPlatformAdmin
                  ? '汇总全平台各团队的凭据（平台管理员权限）'
                  : '汇总您可管理的全部团队凭据'
              }
              onClick={handleSelectCrossTeam}
            >
              {crossTeamTabLabel}
            </Button>
          </div>
          {isCrossTeamView ? (
            <Input
              value={crossTeamSearch}
              onChange={(e) => {
                handleCrossTeamSearchChange(e.target.value)
              }}
              placeholder="按团队名称或 slug 筛选"
              className="h-8 max-w-xs text-sm"
            />
          ) : null}
        </div>
      ) : null}

      {isCrossTeamView && crossTeamData ? (
        <p className="text-xs text-muted-foreground">
          {isPlatformAdmin ? (
            <>
              汇总 {String(crossTeamData.queried_personal_team_count)} 个注册用户工作区 +{' '}
              {String(crossTeamData.queried_shared_team_count)} 个协作团队，共{' '}
              {String(crossTeamData.total)} 条凭据
            </>
          ) : (
            <>
              汇总 {String(crossTeamData.queried_team_count)} 个可管理团队，共{' '}
              {String(crossTeamData.total)} 条凭据
            </>
          )}
        </p>
      ) : null}

      <div className="flex flex-wrap justify-end gap-2">
        {canWrite ? (
          <Button
            variant="outline"
            size="sm"
            onClick={handleImport}
            disabled={mutations.importMutation.isPending}
          >
            导入
          </Button>
        ) : (
          <TooltipProvider delayDuration={200}>
            <Tooltip>
              <TooltipTrigger asChild>
                <span className="inline-flex">
                  <Button size="sm" disabled aria-label="新增团队凭据（需要团队管理员权限）">
                    <Plus className="mr-1.5 h-4 w-4" />
                    新增
                  </Button>
                </span>
              </TooltipTrigger>
              <TooltipContent>需要团队管理员或更高权限</TooltipContent>
            </Tooltip>
          </TooltipProvider>
        )}
        {canWrite && !isCrossTeamView ? (
          <Button
            size="sm"
            onClick={() => {
              onAdd()
            }}
          >
            <Plus className="mr-1.5 h-4 w-4" />
            新增
          </Button>
        ) : null}
      </div>

      <ManagedCredentialsTable
        items={sharedTableItems}
        isLoading={sharedTableLoading}
        routeTeamId={teamId}
        viewMode={isCrossTeamView ? 'cross-team' : 'current-team'}
        showAffiliationColumn={affiliationColumn}
        canWrite={canWrite}
        isAdmin={isAdmin}
        isPlatformAdmin={isPlatformAdmin}
        listVariant="team"
        emptyHint={isCrossTeamView ? '暂无可管理的团队凭据' : '暂无团队凭据'}
        onAdd={onAdd}
        onDelete={deleteFlow.handleDeleteCredential}
        updateMutation={mutations.updateMutation}
      />

      {isCrossTeamView && crossTeamData && crossTeamData.total > crossTeamData.page_size ? (
        <PaginationControls
          page={crossTeamData.page}
          page_size={crossTeamData.page_size}
          total={crossTeamData.total}
          has_next={crossTeamData.has_next}
          has_prev={crossTeamData.has_prev}
          onPageChange={setCrossTeamPage}
        />
      ) : null}

      <CredentialDeleteConfirmDialog
        credential={deleteFlow.credentialPendingDelete}
        isPending={deleteFlow.isDeletePending}
        onOpenChange={deleteFlow.handleDeleteDialogOpenChange}
        onConfirm={deleteFlow.handleDeleteConfirm}
      />
    </TabsContent>
  )
}
