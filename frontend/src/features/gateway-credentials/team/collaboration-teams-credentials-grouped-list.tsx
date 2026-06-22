/**
 * 协作团队 + 凭据分组列表（单表 + 分组行）。
 */

import type React from 'react'

import type { GatewayCredentialUpdateBody, ProviderCredential } from '@/api/gateway'
import type { GatewayTeam } from '@/api/gateway/teams'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { CredentialTableGroupRow } from '@/features/gateway-credentials/components/credential-table-group-row'
import { GatewayCredentialsPanelFallback } from '@/features/gateway-credentials/components/gateway-credentials-panel-fallback'
import { compactCredentialTableColCount } from '@/features/gateway-credentials/credential-table-layout'
import { ManagedCredentialRow } from '@/features/gateway-credentials/managed-credential-row'
import { ManagedCredentialsTableHead } from '@/features/gateway-credentials/managed-credentials-table-head'
import {
  gatewayTeamDisplayLabel,
  gatewayTeamRoleSubtitle,
} from '@/features/gateway-teams/gateway-team-display'
import { isGatewayTeamWritable } from '@/features/gateway-teams/gateway-team-write-policy'
import { useGatewayTeamNameMap } from '@/features/gateway-teams/use-gateway-teams'
import { Plus, Search, Users } from '@/lib/lucide-icons'

export interface CollaborationTeamsCredentialsGroupedListProps {
  teams: readonly GatewayTeam[]
  credentialsByTeamId: ReadonlyMap<string, readonly ProviderCredential[]>
  tenantIdsWithCredentials: ReadonlySet<string>
  requiresSearch: boolean
  isLoading: boolean
  currentPage: number
  isPlatformAdmin: boolean
  viewerUserId?: string | null
  routeTeamId: string
  showEmptyTeams: boolean
  onAddForTeam: (teamId: string) => void
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

function TeamGroupRow({
  team,
  isPlatformAdmin,
  viewerUserId,
  credentialCount,
  onAdd,
}: Readonly<{
  team: GatewayTeam
  isPlatformAdmin: boolean
  viewerUserId?: string | null
  credentialCount: number
  onAdd: () => void
}>): React.JSX.Element {
  const label = gatewayTeamDisplayLabel(team, { viewerUserId })
  const roleSubtitle = gatewayTeamRoleSubtitle(team, isPlatformAdmin)

  return (
    <CredentialTableGroupRow
      icon={Users}
      title={label}
      badges={
        <>
          <Badge variant="outline" className="font-normal">
            {roleSubtitle}
          </Badge>
          <Badge variant="secondary" className="font-normal">
            {credentialCount > 0 ? `${String(credentialCount)} 条凭据` : '暂无凭据'}
          </Badge>
        </>
      }
      actions={
        <Button size="sm" variant="ghost" className="h-7 text-xs" onClick={onAdd}>
          <Plus className="mr-1 h-3.5 w-3.5" />
          添加
        </Button>
      }
    />
  )
}

export function CollaborationTeamsCredentialsGroupedList({
  teams,
  credentialsByTeamId,
  tenantIdsWithCredentials,
  requiresSearch,
  isLoading,
  currentPage,
  isPlatformAdmin,
  viewerUserId,
  routeTeamId,
  showEmptyTeams,
  onAddForTeam,
  onDelete,
  updateMutation,
}: CollaborationTeamsCredentialsGroupedListProps): React.JSX.Element {
  const teamNameById = useGatewayTeamNameMap()

  if (requiresSearch) {
    return (
      <div className="px-4 py-10 text-center">
        <Search className="mx-auto h-8 w-8 text-muted-foreground/60" aria-hidden />
        <h3 className="mt-3 text-base font-semibold">团队数量较多</h3>
        <p className="mt-1 text-sm text-muted-foreground">
          请使用上方搜索框按团队名称筛选，再为对应团队添加凭据。
        </p>
      </div>
    )
  }

  if (isLoading && teams.length === 0) {
    return <GatewayCredentialsPanelFallback />
  }

  const visibleTeams = teams.filter((team) => {
    if (showEmptyTeams) return true
    const rows = credentialsByTeamId.get(team.id) ?? []
    if (rows.length > 0) return true
    return tenantIdsWithCredentials.has(team.id)
  })

  return (
    <ScrollArea className="w-full overscroll-y-contain">
      <table className="w-full min-w-[640px] text-sm">
        <ManagedCredentialsTableHead layout="compact" listVariant="team" />
        <tbody>
          {visibleTeams.map((team) => {
            const teamCredentials = credentialsByTeamId.get(team.id) ?? []
            const hasCredentialsOnServer = tenantIdsWithCredentials.has(team.id)
            const showOffPageHint =
              hasCredentialsOnServer && teamCredentials.length === 0 && currentPage > 1

            return (
              <TeamGroupSection
                key={team.id}
                team={team}
                teamCredentials={teamCredentials}
                showOffPageHint={showOffPageHint}
                hasCredentialsOnServer={hasCredentialsOnServer}
                isPlatformAdmin={isPlatformAdmin}
                viewerUserId={viewerUserId}
                routeTeamId={routeTeamId}
                teamNameById={teamNameById}
                onAddForTeam={onAddForTeam}
                onDelete={onDelete}
                updateMutation={updateMutation}
              />
            )
          })}
          {visibleTeams.length === 0 ? (
            <tr>
              <td
                colSpan={compactCredentialTableColCount(false)}
                className="px-4 py-8 text-center text-sm text-muted-foreground"
              >
                没有匹配的团队
              </td>
            </tr>
          ) : null}
        </tbody>
      </table>
    </ScrollArea>
  )
}

function TeamGroupSection({
  team,
  teamCredentials,
  showOffPageHint,
  hasCredentialsOnServer,
  isPlatformAdmin,
  viewerUserId,
  routeTeamId,
  teamNameById,
  onAddForTeam,
  onDelete,
  updateMutation,
}: Readonly<{
  team: GatewayTeam
  teamCredentials: readonly ProviderCredential[]
  showOffPageHint: boolean
  hasCredentialsOnServer: boolean
  isPlatformAdmin: boolean
  viewerUserId?: string | null
  routeTeamId: string
  teamNameById: Map<string, string>
  onAddForTeam: (teamId: string) => void
  onDelete: (c: ProviderCredential) => void
  updateMutation: CollaborationTeamsCredentialsGroupedListProps['updateMutation']
}>): React.JSX.Element {
  const teamCanWrite = isGatewayTeamWritable(team, isPlatformAdmin)

  return (
    <>
      <TeamGroupRow
        team={team}
        isPlatformAdmin={isPlatformAdmin}
        viewerUserId={viewerUserId}
        credentialCount={teamCredentials.length}
        onAdd={() => {
          onAddForTeam(team.id)
        }}
      />
      {teamCredentials.length > 0
        ? teamCredentials.map((credential) => (
            <ManagedCredentialRow
              key={`${credential.id}:${team.id}`}
              credential={credential}
              routeTeamId={routeTeamId}
              listVariant="team"
              layout="compact"
              showAffiliationColumn={false}
              teamNameById={teamNameById}
              viewerUserId={viewerUserId}
              canWrite={teamCanWrite}
              isPlatformAdmin={isPlatformAdmin}
              listTab="shared"
              onDelete={onDelete}
              updateMutation={updateMutation}
            />
          ))
        : null}
      {teamCredentials.length === 0 ? (
        <tr>
          <td
            colSpan={compactCredentialTableColCount(false)}
            className="px-4 py-2 text-sm text-muted-foreground"
          >
            {showOffPageHint
              ? '该团队已有凭据，请翻页查看。'
              : hasCredentialsOnServer
                ? '该团队已有凭据（见其它页或未匹配当前筛选）。'
                : '暂无凭据'}
          </td>
        </tr>
      ) : null}
    </>
  )
}
