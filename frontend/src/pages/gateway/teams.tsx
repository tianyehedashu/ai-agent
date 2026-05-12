/**
 * AI Gateway · 团队管理
 */

import { useState } from 'react'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2 } from 'lucide-react'

import { gatewayApi, type GatewayTeam, type TeamMember } from '@/api/gateway'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
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
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useToast } from '@/hooks/use-toast'
import { useGatewayTeamStore } from '@/stores/gateway-team'

export default function GatewayTeamsPage(): React.JSX.Element {
  const { canWrite, isPlatformAdmin } = useGatewayPermission()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const currentTeamId = useGatewayTeamStore((s) => s.currentTeamId)

  const { data: teams } = useQuery({
    queryKey: ['gateway', 'teams'],
    queryFn: () => gatewayApi.listTeams(),
  })
  const { data: members } = useQuery({
    queryKey: ['gateway', 'team-members', currentTeamId],
    queryFn: () => (currentTeamId ? gatewayApi.listMembers(currentTeamId) : Promise.resolve([])),
    enabled: !!currentTeamId,
  })

  const [openTeam, setOpenTeam] = useState(false)
  const [openMember, setOpenMember] = useState(false)

  const createTeamMutation = useMutation({
    mutationFn: gatewayApi.createTeam,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'teams'] })
      setOpenTeam(false)
      toast({ title: '团队已创建' })
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '创建失败', description: e.message })
    },
  })
  const deleteTeamMutation = useMutation({
    mutationFn: (id: string) => gatewayApi.deleteTeam(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'teams'] })
    },
  })
  const addMemberMutation = useMutation({
    mutationFn: ({ teamId, ...body }: { teamId: string; user_id: string; role: string }) =>
      gatewayApi.addMember(teamId, { user_id: body.user_id, role: body.role }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'team-members'] })
      setOpenMember(false)
      toast({ title: '成员已添加' })
    },
  })
  const removeMemberMutation = useMutation({
    mutationFn: ({ teamId, userId }: { teamId: string; userId: string }) =>
      gatewayApi.removeMember(teamId, userId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'team-members'] })
    },
  })

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold">团队管理</h2>
          <p className="text-sm text-muted-foreground">个人团队不可删除</p>
        </div>
        {canWrite && (
          <Button
            size="sm"
            onClick={() => {
              setOpenTeam(true)
            }}
          >
            <Plus className="mr-1.5 h-4 w-4" />
            新建团队
          </Button>
        )}
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardContent className="p-0">
            <div className="border-b bg-muted/30 px-4 py-2 text-xs uppercase text-muted-foreground">
              我的团队
            </div>
            <table className="w-full text-sm">
              <tbody>
                {teams?.map((t: GatewayTeam) => (
                  <tr key={t.id} className="border-b last:border-0 hover:bg-muted/20">
                    <td className="px-4 py-2">
                      <div className="font-medium">{t.name}</div>
                      <div className="text-xs text-muted-foreground">
                        {t.kind === 'personal' ? '个人' : (t.team_role ?? 'member')} · {t.slug}
                      </div>
                    </td>
                    <td className="px-4 py-2 text-right">
                      {(isPlatformAdmin || t.team_role === 'owner') && t.kind !== 'personal' && (
                        <Button
                          size="icon"
                          variant="ghost"
                          className="h-7 w-7"
                          onClick={() => {
                            if (confirm(`删除团队 ${t.name}?`)) deleteTeamMutation.mutate(t.id)
                          }}
                        >
                          <Trash2 className="h-3.5 w-3.5 text-destructive" />
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-0">
            <div className="flex items-center justify-between border-b bg-muted/30 px-4 py-2 text-xs uppercase text-muted-foreground">
              <span>当前团队成员</span>
              {canWrite && currentTeamId && (
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
              )}
            </div>
            <table className="w-full text-sm">
              <tbody>
                {(members ?? []).map((m: TeamMember) => (
                  <tr key={m.user_id} className="border-b last:border-0">
                    <td className="px-4 py-2">
                      <div className="font-mono text-xs">{m.user_id}</div>
                      <div className="text-xs text-muted-foreground">{m.role}</div>
                    </td>
                    <td className="px-4 py-2 text-right">
                      {canWrite && m.role !== 'owner' && currentTeamId && (
                        <Button
                          size="icon"
                          variant="ghost"
                          className="h-7 w-7"
                          onClick={() => {
                            removeMemberMutation.mutate({
                              teamId: currentTeamId,
                              userId: m.user_id,
                            })
                          }}
                        >
                          <Trash2 className="h-3.5 w-3.5 text-destructive" />
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
                {(members ?? []).length === 0 && (
                  <tr>
                    <td className="px-4 py-6 text-center text-muted-foreground" colSpan={2}>
                      暂无成员
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </CardContent>
        </Card>
      </div>

      <Dialog open={openTeam} onOpenChange={setOpenTeam}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>新建团队</DialogTitle>
          </DialogHeader>
          <CreateTeamForm
            onSubmit={(v) => {
              createTeamMutation.mutate(v)
            }}
          />
        </DialogContent>
      </Dialog>

      <Dialog open={openMember} onOpenChange={setOpenMember}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>添加成员</DialogTitle>
          </DialogHeader>
          <AddMemberForm
            onSubmit={(v) => {
              if (currentTeamId) {
                addMemberMutation.mutate({ teamId: currentTeamId, ...v })
              }
            }}
          />
        </DialogContent>
      </Dialog>
    </div>
  )
}

function CreateTeamForm({
  onSubmit,
}: Readonly<{
  onSubmit: (v: { name: string; slug?: string }) => void
}>): React.JSX.Element {
  const [name, setName] = useState('')
  const [slug, setSlug] = useState('')
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
        <div>
          <Label>Slug（可选）</Label>
          <Input
            value={slug}
            onChange={(e) => {
              setSlug(e.target.value)
            }}
            placeholder="auto-generated"
          />
        </div>
      </div>
      <DialogFooter>
        <Button
          onClick={() => {
            if (!name) return
            onSubmit({ name, slug: slug || undefined })
          }}
          disabled={!name}
        >
          创建
        </Button>
      </DialogFooter>
    </>
  )
}

function AddMemberForm({
  onSubmit,
}: Readonly<{
  onSubmit: (v: { user_id: string; role: string }) => void
}>): React.JSX.Element {
  const [userId, setUserId] = useState('')
  const [role, setRole] = useState('member')
  return (
    <>
      <div className="space-y-3 py-2">
        <div>
          <Label>用户 ID</Label>
          <Input
            value={userId}
            onChange={(e) => {
              setUserId(e.target.value)
            }}
            placeholder="UUID"
          />
        </div>
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
      </div>
      <DialogFooter>
        <Button
          onClick={() => {
            if (!userId) return
            onSubmit({ user_id: userId, role })
          }}
          disabled={!userId}
        >
          添加
        </Button>
      </DialogFooter>
    </>
  )
}
