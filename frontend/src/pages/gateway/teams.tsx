/**
 * AI Gateway · 团队管理
 */

import { useCallback, useMemo, useState } from 'react'

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Loader2, LogOut, Pencil, Plus, Trash2 } from 'lucide-react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'

import { gatewayApi } from '@/api/gateway'
import type { GatewayTeam, TeamMember } from '@/api/gateway/teams'
import { ConfirmAlertDialog } from '@/components/confirm-alert-dialog'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { credentialsTeamListHref } from '@/features/gateway-models/paths'
import { combineFetching } from '@/features/gateway-shared/combine-fetching'
import { GatewayRefreshButton } from '@/features/gateway-shared/gateway-refresh-button'
import { AddTeamMembersSheet } from '@/features/gateway-teams/add-team-members-sheet'
import { filterCollaborationGatewayTeams } from '@/features/gateway-teams/gateway-team-collaboration'
import { gatewayTeamDisplayLabel } from '@/features/gateway-teams/gateway-team-display'
import { switchGatewayTeam, switchToFallbackTeam } from '@/features/gateway-teams/navigate-team'
import {
  resolveMembersPageFallbackTeamId,
  resolveMembersPageTeamId,
} from '@/features/gateway-teams/resolve-members-page-team-id'
import {
  gatewayTeamMembersQueryKey,
  useGatewayTeamMembers,
} from '@/features/gateway-teams/use-gateway-team-members'
import {
  GATEWAY_MEMBER_TEAMS_QUERY_KEY,
  GATEWAY_TEAMS_QUERY_KEY,
  useGatewayMemberTeams,
} from '@/features/gateway-teams/use-gateway-teams'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useGatewayTeamId } from '@/hooks/use-gateway-team-id'
import { useToast } from '@/hooks/use-toast'
import { cn } from '@/lib/utils'
import { useGatewayTeamStore } from '@/stores/gateway-team'
import { useCurrentUser } from '@/stores/user'
import { formatTeamMemberDisplay, teamRoleLabel, TeamRole } from '@/types/permissions'

import type { QueryClient } from '@tanstack/react-query'
import type { Location, NavigateFunction } from 'react-router-dom'

function membersPageHref(teamId: string): string {
  return `/gateway/teams/${encodeURIComponent(teamId)}/members`
}

function invalidateGatewayTeamQueries(queryClient: QueryClient): void {
  void queryClient.invalidateQueries({ queryKey: GATEWAY_TEAMS_QUERY_KEY })
  void queryClient.invalidateQueries({ queryKey: GATEWAY_MEMBER_TEAMS_QUERY_KEY })
}

function navigateAfterRemovedTeam(
  removedTeamId: string,
  collaborationTeams: readonly GatewayTeam[],
  allTeams: readonly GatewayTeam[],
  navigate: NavigateFunction,
  location: Location,
  queryClient: QueryClient
): void {
  const fallbackTeamId = resolveMembersPageFallbackTeamId(
    collaborationTeams.filter((team) => team.id !== removedTeamId)
  )
  if (fallbackTeamId) {
    switchGatewayTeam(fallbackTeamId, navigate, location, queryClient)
    return
  }
  switchToFallbackTeam(
    allTeams.filter((team) => team.id !== removedTeamId),
    navigate,
    location,
    queryClient
  )
}

export default function GatewayTeamsPage(): React.JSX.Element {
  const teamId = useGatewayTeamId()
  const navigate = useNavigate()
  const location = useLocation()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const { canWrite, isPlatformAdmin, teamRole } = useGatewayPermission()
  const viewerUserId = useCurrentUser()?.id ?? null

  const {
    data: teams,
    isLoading: teamsLoading,
    isError: teamsError,
    isFetching: teamsFetching,
    refetch: refetchTeams,
  } = useGatewayMemberTeams()

  const collaborationTeams = useMemo(() => filterCollaborationGatewayTeams(teams ?? []), [teams])

  const activeCollaborationTeam = collaborationTeams.find((team) => team.id === teamId)
  const membersTeamId = activeCollaborationTeam ? teamId : ''

  const {
    data: members,
    isLoading: membersLoading,
    isError: membersError,
    isFetching: membersFetching,
    refetch: refetchMembers,
  } = useGatewayTeamMembers(membersTeamId)

  const redirectTeamId =
    teamsLoading || teamsError ? null : resolveMembersPageTeamId(teamId, teams ?? [])

  const [openTeam, setOpenTeam] = useState(false)
  const [openMember, setOpenMember] = useState(false)
  const [openRename, setOpenRename] = useState(false)
  const [deleteTeamOpen, setDeleteTeamOpen] = useState(false)
  const [leaveTeamOpen, setLeaveTeamOpen] = useState(false)
  const [pendingDeleteTeam, setPendingDeleteTeam] = useState<{ id: string; name: string } | null>(
    null
  )

  const invalidateMembers = useCallback((): void => {
    if (!membersTeamId) return
    void queryClient.invalidateQueries({ queryKey: gatewayTeamMembersQueryKey(membersTeamId) })
  }, [membersTeamId, queryClient])

  const createTeamMutation = useMutation({
    mutationFn: gatewayApi.createTeam,
    onSuccess: (newTeam) => {
      invalidateGatewayTeamQueries(queryClient)
      setOpenTeam(false)
      switchGatewayTeam(newTeam.id, navigate, location, queryClient)
      toast({ title: '团队已创建', description: `已切换到「${newTeam.name}」` })
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '创建失败', description: e.message })
    },
  })

  const deleteTeamMutation = useMutation({
    mutationFn: (id: string) => gatewayApi.deleteTeam(id),
    onSuccess: (_data, deletedId) => {
      invalidateGatewayTeamQueries(queryClient)
      toast({ title: '团队已删除' })
      if (deletedId === teamId) {
        navigateAfterRemovedTeam(
          deletedId,
          collaborationTeams,
          teams ?? [],
          navigate,
          location,
          queryClient
        )
      }
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '删除失败', description: e.message })
    },
  })

  const updateTeamMutation = useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) => gatewayApi.updateTeam(id, { name }),
    onSuccess: () => {
      invalidateGatewayTeamQueries(queryClient)
      setOpenRename(false)
      toast({ title: '团队名称已更新' })
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '更新失败', description: e.message })
    },
  })

  const updateRoleMutation = useMutation({
    mutationFn: ({
      teamId: tid,
      user_id,
      role,
    }: {
      teamId: string
      user_id: string
      role: string
    }) => gatewayApi.addMember(tid, { user_id, role }),
    onSuccess: () => {
      invalidateMembers()
      toast({ title: '角色已更新' })
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '更新角色失败', description: e.message })
    },
  })

  const removeMemberMutation = useMutation({
    mutationFn: ({ teamId: tid, userId }: { teamId: string; userId: string }) =>
      gatewayApi.removeMember(tid, userId),
    onSuccess: () => {
      invalidateMembers()
      toast({ title: '成员已移除' })
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '移除失败', description: e.message })
    },
  })

  const leaveTeamMutation = useMutation({
    mutationFn: (tid: string) => gatewayApi.leaveTeam(tid),
    onSuccess: () => {
      invalidateGatewayTeamQueries(queryClient)
      invalidateMembers()
      setLeaveTeamOpen(false)
      toast({ title: '已退出团队' })
      navigateAfterRemovedTeam(
        teamId,
        collaborationTeams,
        teams ?? [],
        navigate,
        location,
        queryClient
      )
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '退出失败', description: e.message })
    },
  })

  const cachedTeams = useGatewayTeamStore((s) => s.teams)
  const currentTeamFromApi = activeCollaborationTeam
  const currentTeam =
    currentTeamFromApi ?? cachedTeams.find((team) => team.id === teamId && team.kind === 'shared')
  const canAddMember = Boolean(canWrite && membersTeamId && currentTeamFromApi)
  const canRenameTeam = Boolean(canWrite && currentTeamFromApi)
  const canLeaveTeam = Boolean(
    currentTeamFromApi && teamRole !== TeamRole.OWNER && !isPlatformAdmin
  )

  if (redirectTeamId) {
    return <Navigate to={membersPageHref(redirectTeamId)} replace />
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold">团队管理</h2>
          <p className="text-sm text-muted-foreground">管理共享团队与成员协作</p>
        </div>
        <div className="flex items-center gap-2">
          <GatewayRefreshButton
            isFetching={combineFetching(teamsFetching, membersFetching)}
            ariaLabel="刷新团队"
            onRefresh={() => {
              void Promise.all([refetchTeams(), refetchMembers()])
            }}
          />
          {canLeaveTeam ? (
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                setLeaveTeamOpen(true)
              }}
            >
              <LogOut className="mr-1.5 h-4 w-4" />
              退出团队
            </Button>
          ) : null}
          {canWrite ? (
            <Button
              size="sm"
              onClick={() => {
                setOpenTeam(true)
              }}
            >
              <Plus className="mr-1.5 h-4 w-4" />
              新建团队
            </Button>
          ) : null}
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardContent className="p-0">
            <div className="border-b bg-muted/30 px-4 py-2 text-xs uppercase text-muted-foreground">
              我的团队
            </div>
            {teamsLoading ? (
              <div className="flex items-center justify-center gap-2 px-4 py-8 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                加载中…
              </div>
            ) : teamsError ? (
              <p className="px-4 py-8 text-center text-sm text-destructive">加载团队列表失败</p>
            ) : (
              <table className="w-full text-sm">
                <tbody>
                  {collaborationTeams.map((t: GatewayTeam) => {
                    const isActive = t.id === teamId
                    const roleLabel = teamRoleLabel(t.team_role ?? 'member')
                    const canDelete = isPlatformAdmin || t.team_role === 'owner'
                    const canEdit = canWrite && isActive

                    return (
                      <tr
                        key={t.id}
                        className={cn(
                          'border-b last:border-0 hover:bg-muted/20',
                          isActive && 'bg-muted/30'
                        )}
                      >
                        <td className="px-4 py-2">
                          <button
                            type="button"
                            className="w-full text-left"
                            onClick={() => {
                              switchGatewayTeam(t.id, navigate, location, queryClient)
                            }}
                          >
                            <div className="font-medium">
                              {gatewayTeamDisplayLabel(t, { viewerUserId })}
                            </div>
                            <div className="text-xs text-muted-foreground">{roleLabel}</div>
                          </button>
                        </td>
                        <td className="px-4 py-2 text-right">
                          <div className="flex items-center justify-end gap-1">
                            {canEdit ? (
                              <Button
                                size="icon"
                                variant="ghost"
                                className="h-7 w-7"
                                onClick={() => {
                                  setOpenRename(true)
                                }}
                              >
                                <Pencil className="h-3.5 w-3.5" />
                              </Button>
                            ) : null}
                            {canDelete ? (
                              <Button
                                size="icon"
                                variant="ghost"
                                className="h-7 w-7"
                                onClick={() => {
                                  setPendingDeleteTeam({ id: t.id, name: t.name })
                                  setDeleteTeamOpen(true)
                                }}
                              >
                                <Trash2 className="h-3.5 w-3.5 text-destructive" />
                              </Button>
                            ) : null}
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                  {collaborationTeams.length === 0 ? (
                    <tr>
                      <td className="px-4 py-6 text-center text-muted-foreground" colSpan={2}>
                        暂无共享团队
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-0">
            <div className="flex items-center justify-between border-b bg-muted/30 px-4 py-2 text-xs uppercase text-muted-foreground">
              <span>
                {currentTeamFromApi
                  ? gatewayTeamDisplayLabel(currentTeamFromApi, { viewerUserId })
                  : '选择或新建共享团队'}
              </span>
              <div className="flex items-center gap-2 normal-case">
                {membersTeamId ? (
                  <Link
                    to={credentialsTeamListHref(membersTeamId)}
                    className="text-primary underline-offset-4 hover:underline"
                  >
                    查看凭据
                  </Link>
                ) : null}
                {canAddMember ? (
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-6 text-xs"
                    onClick={() => {
                      setOpenMember(true)
                    }}
                  >
                    <Plus className="mr-1 h-3 w-3" />
                    添加
                  </Button>
                ) : null}
              </div>
            </div>
            {!membersTeamId ? (
              <p className="px-4 py-8 text-center text-sm text-muted-foreground">
                {collaborationTeams.length === 0
                  ? '暂无共享团队，请先新建团队'
                  : '请选择左侧共享团队'}
              </p>
            ) : membersLoading ? (
              <div className="flex items-center justify-center gap-2 px-4 py-8 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                加载中…
              </div>
            ) : membersError ? (
              <p className="px-4 py-8 text-center text-sm text-destructive">加载成员列表失败</p>
            ) : (
              <table className="w-full text-sm">
                <tbody>
                  {(members ?? []).map((m: TeamMember) => {
                    const display = formatTeamMemberDisplay(m)
                    const canEditRole = canWrite && m.role !== TeamRole.OWNER && m.role !== 'owner'
                    const canRemove = canWrite && m.role !== TeamRole.OWNER && m.role !== 'owner'

                    return (
                      <tr key={m.user_id} className="border-b last:border-0">
                        <td className="px-4 py-2">
                          <div className="font-medium">{display.primary}</div>
                          <div className="text-xs text-muted-foreground">{display.secondary}</div>
                        </td>
                        <td className="px-4 py-2 text-right">
                          <div className="flex items-center justify-end gap-2">
                            {canEditRole && teamId ? (
                              <Select
                                value={m.role === TeamRole.ADMIN ? TeamRole.ADMIN : TeamRole.MEMBER}
                                onValueChange={(role) => {
                                  updateRoleMutation.mutate({
                                    teamId,
                                    user_id: m.user_id,
                                    role,
                                  })
                                }}
                              >
                                <SelectTrigger className="h-7 w-[88px] text-xs">
                                  <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                  <SelectItem value={TeamRole.MEMBER}>成员</SelectItem>
                                  <SelectItem value={TeamRole.ADMIN}>管理员</SelectItem>
                                </SelectContent>
                              </Select>
                            ) : (
                              <span className="text-xs text-muted-foreground">
                                {teamRoleLabel(m.role)}
                              </span>
                            )}
                            {canRemove && teamId ? (
                              <Button
                                size="icon"
                                variant="ghost"
                                className="h-7 w-7"
                                onClick={() => {
                                  removeMemberMutation.mutate({
                                    teamId,
                                    userId: m.user_id,
                                  })
                                }}
                              >
                                <Trash2 className="h-3.5 w-3.5 text-destructive" />
                              </Button>
                            ) : null}
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                  {(members ?? []).length === 0 ? (
                    <tr>
                      <td className="px-4 py-6 text-center text-muted-foreground" colSpan={2}>
                        暂无成员
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            )}
          </CardContent>
        </Card>
      </div>

      <Dialog open={openTeam} onOpenChange={setOpenTeam}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>新建团队</DialogTitle>
            <DialogDescription>创建团队后可添加成员并分配 Gateway 权限。</DialogDescription>
          </DialogHeader>
          {openTeam ? (
            <CreateTeamForm
              onSubmit={(v) => {
                createTeamMutation.mutate(v)
              }}
              pending={createTeamMutation.isPending}
            />
          ) : null}
        </DialogContent>
      </Dialog>

      <Dialog open={openRename} onOpenChange={setOpenRename}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>重命名团队</DialogTitle>
            <DialogDescription>修改当前共享团队的显示名称。</DialogDescription>
          </DialogHeader>
          {currentTeam && canRenameTeam ? (
            <RenameTeamForm
              key={currentTeam.id}
              initialName={currentTeam.name}
              pending={updateTeamMutation.isPending}
              onSubmit={(name) => {
                updateTeamMutation.mutate({ id: currentTeam.id, name })
              }}
            />
          ) : null}
        </DialogContent>
      </Dialog>

      <AddTeamMembersSheet
        open={openMember}
        onOpenChange={setOpenMember}
        teamId={membersTeamId}
        team={currentTeamFromApi}
        teamRole={teamRole}
        onMembersAdded={invalidateMembers}
      />

      <ConfirmAlertDialog
        open={deleteTeamOpen}
        onOpenChange={(open) => {
          setDeleteTeamOpen(open)
          if (!open) setPendingDeleteTeam(null)
        }}
        title="删除团队"
        description={
          pendingDeleteTeam
            ? `确定删除团队「${pendingDeleteTeam.name}」？此操作不可撤销。`
            : '确定删除该团队？'
        }
        confirmLabel="确认删除"
        pending={deleteTeamMutation.isPending}
        onConfirm={() => {
          if (!pendingDeleteTeam) return
          const id = pendingDeleteTeam.id
          setDeleteTeamOpen(false)
          setPendingDeleteTeam(null)
          deleteTeamMutation.mutate(id)
        }}
      />

      <ConfirmAlertDialog
        open={leaveTeamOpen}
        onOpenChange={setLeaveTeamOpen}
        title="退出团队"
        description={
          currentTeam
            ? `确定退出团队「${currentTeam.name}」？退出后将无法访问该团队的 Gateway 资源。`
            : '确定退出当前团队？'
        }
        confirmLabel="确认退出"
        pending={leaveTeamMutation.isPending}
        onConfirm={() => {
          if (teamId) leaveTeamMutation.mutate(teamId)
        }}
      />
    </div>
  )
}

function CreateTeamForm({
  onSubmit,
  pending,
}: Readonly<{
  onSubmit: (v: { name: string }) => void
  pending?: boolean
}>): React.JSX.Element {
  const [name, setName] = useState('')
  return (
    <>
      <div className="space-y-3 py-2">
        <div>
          <Label>团队名称</Label>
          <Input
            value={name}
            onChange={(e) => {
              setName(e.target.value)
            }}
            placeholder="例如：产品团队"
          />
        </div>
      </div>
      <DialogFooter>
        <Button
          onClick={() => {
            if (!name) return
            onSubmit({ name })
          }}
          disabled={!name || pending}
        >
          {pending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
          创建
        </Button>
      </DialogFooter>
    </>
  )
}

function RenameTeamForm({
  initialName,
  onSubmit,
  pending,
}: Readonly<{
  initialName: string
  onSubmit: (name: string) => void
  pending?: boolean
}>): React.JSX.Element {
  const [name, setName] = useState(initialName)

  return (
    <>
      <div className="space-y-3 py-2">
        <div>
          <Label>名称</Label>
          <Input
            value={name}
            onChange={(e) => {
              setName(e.target.value)
            }}
          />
        </div>
      </div>
      <DialogFooter>
        <Button
          onClick={() => {
            const trimmed = name.trim()
            if (!trimmed) return
            onSubmit(trimmed)
          }}
          disabled={!name.trim() || pending}
        >
          {pending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
          保存
        </Button>
      </DialogFooter>
    </>
  )
}
