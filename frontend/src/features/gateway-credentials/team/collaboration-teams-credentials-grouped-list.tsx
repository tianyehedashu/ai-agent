/**
 * 协作团队 + 凭据分组列表。
 */

import type React from 'react'

import type { GatewayCredentialUpdateBody, ProviderCredential } from '@/api/gateway'
import type { GatewayTeam } from '@/api/gateway/teams'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { ManagedCredentialRow } from '@/features/gateway-credentials/managed-credential-row'
import { CollaborationTeamGroupHeader } from '@/features/gateway-teams/collaboration-team-group-header'
import { Plus, Search } from '@/lib/lucide-icons'

export interface CollaborationTeamsCredentialsGroupedListProps {
  teams: readonly GatewayTeam[]
  credentialsByTeamId: ReadonlyMap<string, readonly ProviderCredential[]>
  tenantIdsWithCredentials: ReadonlySet<string>
  requiresSearch: boolean
  isLoading: boolean
  currentPage: number
  canWrite: boolean
  isAdmin: boolean
  isPlatformAdmin: boolean
  viewerUserId?: string | null
  routeTeamId: string
  importPendingTeamId?: string | null
  onAddForTeam: (teamId: string) => void
  onImportForTeam: (teamId: string) => void
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

export function CollaborationTeamsCredentialsGroupedList({
  teams,
  credentialsByTeamId,
  tenantIdsWithCredentials,
  requiresSearch,
  isLoading,
  currentPage,
  canWrite,
  isAdmin,
  isPlatformAdmin,
  viewerUserId,
  routeTeamId,
  importPendingTeamId,
  onAddForTeam,
  onImportForTeam,
  onDelete,
  updateMutation,
}: CollaborationTeamsCredentialsGroupedListProps): React.JSX.Element {
  if (requiresSearch) {
    return (
      <div className="px-4 py-10 text-center">
        <Search className="mx-auto h-8 w-8 text-muted-foreground/60" aria-hidden />
        <h3 className="mt-3 text-base font-semibold">团队数量较多</h3>
        <p className="mt-1 text-sm text-muted-foreground">
          请使用上方搜索框按团队名称或 slug 筛选，再为对应团队添加凭据。
        </p>
      </div>
    )
  }

  if (isLoading && teams.length === 0) {
    return <div className="px-4 py-12 text-center text-sm text-muted-foreground">加载中…</div>
  }

  return (
    <ScrollArea className="max-h-[min(70vh,720px)] w-full overscroll-y-contain">
      <div className="divide-y">
        {teams.map((team) => {
          const teamCredentials = credentialsByTeamId.get(team.id) ?? []
          const hasCredentialsOnServer = tenantIdsWithCredentials.has(team.id)
          const showOffPageHint =
            hasCredentialsOnServer && teamCredentials.length === 0 && currentPage > 1

          return (
            <section key={team.id} aria-label={`团队 ${team.name} 凭据`}>
              <CollaborationTeamGroupHeader
                team={team}
                isPlatformAdmin={isPlatformAdmin}
                viewerUserId={viewerUserId}
                actions={
                  canWrite ? (
                    <>
                      <Button
                        variant="outline"
                        size="sm"
                        className="h-7 text-xs"
                        disabled={importPendingTeamId === team.id}
                        onClick={() => {
                          onImportForTeam(team.id)
                        }}
                      >
                        {importPendingTeamId === team.id ? '导入中…' : '从配置导入'}
                      </Button>
                      <Button
                        size="sm"
                        className="h-7 text-xs"
                        onClick={() => {
                          onAddForTeam(team.id)
                        }}
                      >
                        <Plus className="mr-1 h-3.5 w-3.5" />
                        添加凭据
                      </Button>
                    </>
                  ) : null
                }
              />
              {teamCredentials.length > 0 ? (
                <table className="w-full min-w-[720px] text-sm">
                  <thead className="border-b bg-muted/10 text-xs uppercase text-muted-foreground">
                    <tr>
                      <th className="px-4 py-2 text-left font-medium">名称</th>
                      <th className="px-4 py-2 text-left font-medium">API Key</th>
                      <th className="px-4 py-2 text-left font-medium">提供商</th>
                      <th className="px-4 py-2 text-left font-medium">作用域</th>
                      <th className="px-4 py-2 text-left font-medium">api_base</th>
                      <th className="px-4 py-2 text-left font-medium">启用</th>
                      <th className="px-4 py-2 text-left font-medium">操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {teamCredentials.map((credential) => (
                      <ManagedCredentialRow
                        key={`${credential.id}:${team.id}`}
                        credential={credential}
                        routeTeamId={routeTeamId}
                        listVariant="team"
                        showAffiliationColumn={false}
                        canWrite={canWrite}
                        isAdmin={isAdmin}
                        isPlatformAdmin={isPlatformAdmin}
                        onDelete={onDelete}
                        updateMutation={updateMutation}
                      />
                    ))}
                  </tbody>
                </table>
              ) : showOffPageHint ? (
                <p className="px-4 py-3 text-sm text-muted-foreground">
                  该团队已有凭据，请翻页查看。
                </p>
              ) : hasCredentialsOnServer && teamCredentials.length === 0 ? (
                <p className="px-4 py-3 text-sm text-muted-foreground">
                  该团队已有凭据（见其它页或未匹配当前筛选）。
                </p>
              ) : (
                <p className="px-4 py-3 text-sm text-muted-foreground">暂无凭据</p>
              )}
            </section>
          )
        })}
        {teams.length === 0 ? (
          <div className="px-4 py-8 text-center text-sm text-muted-foreground">没有匹配的团队</div>
        ) : null}
      </div>
    </ScrollArea>
  )
}
