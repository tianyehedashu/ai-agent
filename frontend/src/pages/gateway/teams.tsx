/**
 * AI Gateway · 团队管理
 */

import { useState } from 'react'

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Loader2, LogOut, Pencil, Plus, Search, Trash2 } from 'lucide-react'
import { useLocation, useNavigate, Link } from 'react-router-dom'

import { gatewayApi } from '@/api/gateway'
import type { GatewayTeam, TeamMember, TeamMemberLookup } from '@/api/gateway/teams'
import { ConfirmAlertDialog } from '@/components/confirm-alert-dialog'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
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
import {
  GATEWAY_TEAMS_QUERY_KEY,
  useGatewayTeams,
} from '@/features/api-key-gateway/use-gateway-teams'
import { credentialsTeamListHref } from '@/features/gateway-models/paths'
import { combineFetching } from '@/features/gateway-shared/combine-fetching'
import { GatewayRefreshButton } from '@/features/gateway-shared/gateway-refresh-button'
import { gatewayTeamDisplayLabel } from '@/features/gateway-teams/gateway-team-display'
import { switchGatewayTeam, switchToFallbackTeam } from '@/features/gateway-teams/navigate-team'
import {
  gatewayTeamMembersQueryKey,
  useGatewayTeamMembers,
} from '@/features/gateway-teams/use-gateway-team-members'
import { useGatewayMemberTeams } from '@/features/gateway-teams/use-gateway-teams'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useGatewayTeamId } from '@/hooks/use-gateway-team-id'
import { useToast } from '@/hooks/use-toast'
import { cn } from '@/lib/utils'
import { useGatewayTeamStore } from '@/stores/gateway-team'
import { useUserStore } from '@/stores/user'
import { formatTeamMemberDisplay, teamRoleLabel, TeamRole } from '@/types/permissions'

export default function GatewayTeamsPage(): React.JSX.Element {
  const teamId = useGatewayTeamId()
  const navigate = useNavigate()
  const location = useLocation()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const { canWrite, isPlatformAdmin, teamRole } = useGatewayPermission()
  const viewerUserId = useUserStore((s) => s.currentUser?.id ?? null)

  const {
    data: teams,
    isLoading: teamsLoading,
    isError: teamsError,
    isFetching: teamsFetching,
    refetch: refetchTeams,
  } = useGatewayTeams()

  const { isFetching: memberTeamsFetching, refetch: refetchMemberTeams } = useGatewayMemberTeams()

  const {
    data: members,
    isLoading: membersLoading,
    isError: membersError,
    isFetching: membersFetching,
    refetch: refetchMembers,
  } = useGatewayTeamMembers(teamId)

  const [openTeam, setOpenTeam] = useState(false)
  const [openMember, setOpenMember] = useState(false)
  const [openRename, setOpenRename] = useState(false)
  const [deleteTeamOpen, setDeleteTeamOpen] = useState(false)
  const [leaveTeamOpen, setLeaveTeamOpen] = useState(false)
  const [pendingDeleteTeam, setPendingDeleteTeam] = useState<{ id: string; name: string } | null>(
    null
  )

  const invalidateMembers = (): void => {
    void queryClient.invalidateQueries({ queryKey: gatewayTeamMembersQueryKey(teamId) })
  }

  const createTeamMutation = useMutation({
    mutationFn: gatewayApi.createTeam,
    onSuccess: (newTeam) => {
      void queryClient.invalidateQueries({ queryKey: GATEWAY_TEAMS_QUERY_KEY })
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
      void queryClient.invalidateQueries({ queryKey: GATEWAY_TEAMS_QUERY_KEY })
      toast({ title: '团队已删除' })
      if (deletedId === teamId) {
        const cached = queryClient.getQueryData<GatewayTeam[]>(GATEWAY_TEAMS_QUERY_KEY)
        const remaining = (cached ?? []).filter((t) => t.id !== deletedId)
        switchToFallbackTeam(remaining, navigate, location, queryClient)
      }
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '删除失败', description: e.message })
    },
  })

  const updateTeamMutation = useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) => gatewayApi.updateTeam(id, { name }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: GATEWAY_TEAMS_QUERY_KEY })
      setOpenRename(false)
      toast({ title: '团队名称已更新' })
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '更新失败', description: e.message })
    },
  })

  const addMemberMutation = useMutation({
    mutationFn: ({ teamId: tid, ...body }: { teamId: string; user_id: string; role: string }) =>
      gatewayApi.addMember(tid, { user_id: body.user_id, role: body.role }),
    onSuccess: () => {
      invalidateMembers()
      setOpenMember(false)
      toast({ title: '成员已添加' })
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '添加失败', description: e.message })
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
      void queryClient.invalidateQueries({ queryKey: GATEWAY_TEAMS_QUERY_KEY })
      invalidateMembers()
      setLeaveTeamOpen(false)
      toast({ title: '已退出团队' })
      const cached = queryClient.getQueryData<GatewayTeam[]>(GATEWAY_TEAMS_QUERY_KEY)
      const remaining = (cached ?? []).filter((t) => t.id !== teamId)
      switchToFallbackTeam(remaining, navigate, location, queryClient)
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '退出失败', description: e.message })
    },
  })

  const cachedTeams = useGatewayTeamStore((s) => s.teams)
  const currentTeamFromApi = teams?.find((t) => t.id === teamId)
  const currentTeam = currentTeamFromApi ?? cachedTeams.find((t) => t.id === teamId)
  const isPersonalTeam = currentTeam?.kind === 'personal'
  const canAddMember = Boolean(canWrite && teamId && currentTeam && !isPersonalTeam)
  const canRenameTeam = Boolean(canWrite && currentTeam && !isPersonalTeam)
  const canLeaveTeam = Boolean(
    currentTeam && !isPersonalTeam && teamRole !== TeamRole.OWNER && !isPlatformAdmin
  )

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold">团队管理</h2>
          <p className="text-sm text-muted-foreground">个人团队不可删除；共享团队可协作管理</p>
        </div>
        <div className="flex items-center gap-2">
          <GatewayRefreshButton
            isFetching={combineFetching(teamsFetching, membersFetching, memberTeamsFetching)}
            ariaLabel="刷新团队"
            onRefresh={() => {
              void Promise.all([refetchTeams(), refetchMembers(), refetchMemberTeams()])
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
                  {teams?.map((t: GatewayTeam) => {
                    const isActive = t.id === teamId
                    const roleLabel =
                      t.kind === 'personal' ? '个人' : teamRoleLabel(t.team_role ?? 'member')
                    const canDelete =
                      (isPlatformAdmin || t.team_role === 'owner') && t.kind !== 'personal'
                    const canEdit = canWrite && t.kind !== 'personal' && isActive

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
                  {(teams ?? []).length === 0 ? (
                    <tr>
                      <td className="px-4 py-6 text-center text-muted-foreground" colSpan={2}>
                        暂无团队
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
                  : currentTeam?.kind === 'personal'
                    ? '个人工作区'
                    : (currentTeam?.name ?? '当前团队成员')}
              </span>
              <div className="flex items-center gap-2 normal-case">
                {teamId ? (
                  <Link
                    to={credentialsTeamListHref(teamId)}
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
            {isPersonalTeam ? (
              <p className="border-b px-4 py-2 text-xs text-muted-foreground">
                个人工作区仅本人可见，个人凭据与模型不会共享给其他用户。如需协作请新建共享团队并添加成员。
              </p>
            ) : null}
            {membersLoading ? (
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

      <Dialog open={openMember} onOpenChange={setOpenMember}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>添加成员</DialogTitle>
            <DialogDescription>通过邮箱查找已注册用户并加入当前团队。</DialogDescription>
          </DialogHeader>
          {openMember && teamId ? (
            <AddMemberForm
              key={teamId}
              teamId={teamId}
              pending={addMemberMutation.isPending}
              onSubmit={(v) => {
                addMemberMutation.mutate({ teamId, ...v })
              }}
            />
          ) : null}
        </DialogContent>
      </Dialog>

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

function AddMemberForm({
  teamId,
  onSubmit,
  pending,
}: Readonly<{
  teamId: string
  onSubmit: (v: { user_id: string; role: string }) => void
  pending?: boolean
}>): React.JSX.Element {
  const { toast } = useToast()
  const [email, setEmail] = useState('')
  const [role, setRole] = useState('member')
  const [foundUser, setFoundUser] = useState<TeamMemberLookup | null>(null)
  const [isLookingUp, setIsLookingUp] = useState(false)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [userId, setUserId] = useState('')

  const handleLookup = async (): Promise<void> => {
    const trimmed = email.trim()
    if (!trimmed) {
      toast({ variant: 'destructive', title: '请输入邮箱' })
      return
    }
    setIsLookingUp(true)
    setFoundUser(null)
    try {
      const user = await gatewayApi.lookupMemberByEmail(teamId, trimmed)
      setFoundUser(user)
    } catch (error) {
      toast({
        variant: 'destructive',
        title: '查找失败',
        description: error instanceof Error ? error.message : '用户不存在',
      })
    } finally {
      setIsLookingUp(false)
    }
  }

  const handleSubmit = (): void => {
    const id = foundUser?.id ?? userId.trim()
    if (!id) {
      toast({ variant: 'destructive', title: '请先查找用户或输入用户 ID' })
      return
    }
    onSubmit({ user_id: id, role })
  }

  return (
    <>
      <div className="space-y-3 py-2">
        <div className="flex gap-2">
          <div className="flex-1">
            <Label>邮箱</Label>
            <Input
              value={email}
              onChange={(e) => {
                setEmail(e.target.value)
                setFoundUser(null)
              }}
              placeholder="user@example.com"
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault()
                  void handleLookup()
                }
              }}
            />
          </div>
          <div className="flex items-end">
            <Button
              type="button"
              variant="secondary"
              disabled={isLookingUp}
              onClick={() => void handleLookup()}
            >
              {isLookingUp ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Search className="h-4 w-4" />
              )}
              <span className="ml-1.5">查找</span>
            </Button>
          </div>
        </div>

        {foundUser ? (
          <div className="rounded-md border bg-muted/30 px-3 py-2 text-sm">
            <div className="font-medium">{foundUser.name ?? foundUser.email}</div>
            <div className="text-xs text-muted-foreground">{foundUser.email}</div>
          </div>
        ) : null}

        <div>
          <Label>角色</Label>
          <Select value={role} onValueChange={setRole}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="member">成员</SelectItem>
              <SelectItem value="admin">管理员</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <Collapsible open={showAdvanced} onOpenChange={setShowAdvanced}>
          <CollapsibleTrigger asChild>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-7 px-0 text-xs text-muted-foreground"
            >
              高级：直接输入用户 ID
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent className="pt-2">
            <Label>用户 ID</Label>
            <Input
              value={userId}
              onChange={(e) => {
                setUserId(e.target.value)
              }}
              placeholder="UUID"
            />
          </CollapsibleContent>
        </Collapsible>
      </div>
      <DialogFooter>
        <Button onClick={handleSubmit} disabled={pending ? true : !foundUser && !userId.trim()}>
          {pending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
          添加
        </Button>
      </DialogFooter>
    </>
  )
}
