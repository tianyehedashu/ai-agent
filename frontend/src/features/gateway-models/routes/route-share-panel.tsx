/**
 * 路由共享面板（owner 侧）
 *
 * 把"个人路由"发布给协作团队（委派模式：被授权团队以本路由 owner 身份解析底层模型，
 * 用量计入消费团队、归因到 owner）。展示已发布团队芯片 + 撤销，并提供发布对话框。
 */

import { useState } from 'react'

import type { RouteGrant } from '@/api/gateway/routes'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
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
  useGrantRouteToTeam,
  useRevokeRouteGrant,
  useRouteGrantableTeams,
  useRouteGrants,
  useUpdateRouteGrantAlias,
} from '@/features/gateway-models/hooks/use-route-grants'
import { useToast } from '@/hooks/use-toast'
import { Loader2, Pencil, Share2, Users, X } from '@/lib/lucide-icons'

interface RouteSharePanelProps {
  routeId: string
  virtualModel: string
}

export function RouteSharePanel({
  routeId,
  virtualModel,
}: RouteSharePanelProps): React.JSX.Element {
  const { toast } = useToast()
  const { data: grants = [], isLoading } = useRouteGrants(routeId)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingGrant, setEditingGrant] = useState<RouteGrant | null>(null)
  const revokeMutation = useRevokeRouteGrant(routeId)

  function handleRevoke(tenantId: string, teamName: string): void {
    revokeMutation.mutate(tenantId, {
      onSuccess: () => {
        toast({ title: `已取消对「${teamName}」的共享` })
      },
      onError: (e: Error) => {
        toast({ variant: 'destructive', title: '撤销失败', description: e.message })
      },
    })
  }

  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-sm font-medium">
          <Share2 className="h-4 w-4 text-muted-foreground" />
          共享给团队
        </div>
        <Button
          size="sm"
          variant="outline"
          onClick={() => {
            setDialogOpen(true)
          }}
        >
          <Share2 className="mr-1.5 h-3.5 w-3.5" />
          发布
        </Button>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">
        被授权团队可用暴露别名直接调用本路由；底层以你的身份解析模型，用量计入消费团队并归因到你。
      </p>

      <div className="mt-3">
        {isLoading ? (
          <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
        ) : grants.length === 0 ? (
          <p className="text-xs text-muted-foreground">尚未共享给任何团队。</p>
        ) : (
          <ul className="flex flex-wrap gap-2">
            {grants.map((grant) => {
              const teamName = grant.granted_team_name ?? grant.tenant_id.slice(0, 8)
              return (
                <li key={grant.id}>
                  <Badge variant="secondary" className="gap-1.5 py-1 pl-2 pr-1 font-normal">
                    <Users className="h-3 w-3 text-muted-foreground" />
                    <span className="max-w-[160px] truncate">{teamName}</span>
                    <span className="font-mono text-[10px] text-muted-foreground">
                      {grant.exposed_alias}
                    </span>
                    <button
                      type="button"
                      aria-label={`修改「${teamName}」的暴露别名`}
                      className="ml-0.5 rounded-sm p-0.5 hover:bg-muted-foreground/20"
                      onClick={() => {
                        setEditingGrant(grant)
                      }}
                    >
                      <Pencil className="h-3 w-3" />
                    </button>
                    <button
                      type="button"
                      aria-label={`取消共享给 ${teamName}`}
                      className="rounded-sm p-0.5 hover:bg-muted-foreground/20 disabled:opacity-50"
                      disabled={revokeMutation.isPending}
                      onClick={() => {
                        handleRevoke(grant.tenant_id, teamName)
                      }}
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </Badge>
                </li>
              )
            })}
          </ul>
        )}
      </div>

      <RouteShareDialog
        routeId={routeId}
        virtualModel={virtualModel}
        open={dialogOpen}
        onOpenChange={setDialogOpen}
      />

      {editingGrant ? (
        <RouteGrantAliasDialog
          key={editingGrant.id}
          routeId={routeId}
          grant={editingGrant}
          onClose={() => {
            setEditingGrant(null)
          }}
        />
      ) : null}
    </div>
  )
}

interface RouteGrantAliasDialogProps {
  routeId: string
  grant: RouteGrant
  onClose: () => void
}

function RouteGrantAliasDialog({
  routeId,
  grant,
  onClose,
}: RouteGrantAliasDialogProps): React.JSX.Element {
  const { toast } = useToast()
  const updateMutation = useUpdateRouteGrantAlias(routeId)
  const [alias, setAlias] = useState(grant.exposed_alias)

  function handleSubmit(): void {
    const trimmed = alias.trim()
    if (trimmed.length === 0) {
      toast({ variant: 'destructive', title: '别名不能为空' })
      return
    }
    if (trimmed === grant.exposed_alias) {
      onClose()
      return
    }
    updateMutation.mutate(
      { tenantId: grant.tenant_id, exposed_alias: trimmed },
      {
        onSuccess: () => {
          toast({ title: '暴露别名已更新' })
          onClose()
        },
        onError: (e: Error) => {
          toast({ variant: 'destructive', title: '更新失败', description: e.message })
        },
      }
    )
  }

  const teamName = grant.granted_team_name ?? grant.tenant_id.slice(0, 8)

  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) onClose()
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>修改暴露别名</DialogTitle>
          <DialogDescription>
            团队「{teamName}
            」的成员将以新别名调用本路由（团队内唯一，不能与该团队本地模型/路由重名）。
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-1.5">
          <Label>暴露别名</Label>
          <Input
            value={alias}
            onChange={(e) => {
              setAlias(e.target.value)
            }}
            className="font-mono"
            autoFocus
          />
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>
            取消
          </Button>
          <Button onClick={handleSubmit} disabled={updateMutation.isPending}>
            {updateMutation.isPending ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" /> : null}
            保存
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

interface RouteShareDialogProps {
  routeId: string
  virtualModel: string
  open: boolean
  onOpenChange: (open: boolean) => void
}

function RouteShareDialog({
  routeId,
  virtualModel,
  open,
  onOpenChange,
}: RouteShareDialogProps): React.JSX.Element {
  const { toast } = useToast()
  const { data: teams = [], isLoading } = useRouteGrantableTeams(routeId, { enabled: open })
  const grantMutation = useGrantRouteToTeam(routeId)
  const [teamId, setTeamId] = useState('')
  const [alias, setAlias] = useState('')

  function reset(): void {
    setTeamId('')
    setAlias('')
  }

  function handleSubmit(): void {
    if (!teamId) {
      toast({ variant: 'destructive', title: '请选择目标团队' })
      return
    }
    const trimmed = alias.trim()
    grantMutation.mutate(
      { target_tenant_id: teamId, exposed_alias: trimmed.length > 0 ? trimmed : null },
      {
        onSuccess: () => {
          toast({ title: '路由已发布' })
          reset()
          onOpenChange(false)
        },
        onError: (e: Error) => {
          toast({ variant: 'destructive', title: '发布失败', description: e.message })
        },
      }
    )
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) reset()
        onOpenChange(next)
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>发布路由「{virtualModel}」</DialogTitle>
          <DialogDescription>
            选择协作团队并设置暴露别名（留空则沿用路由虚拟名）。被授权团队成员即可在其
            <span className="font-mono"> /v1/models </span>列表与对话中使用该别名。
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <div className="space-y-1.5">
            <Label>目标团队</Label>
            <Select value={teamId} onValueChange={setTeamId} disabled={isLoading}>
              <SelectTrigger>
                <SelectValue placeholder={isLoading ? '加载中…' : '选择团队'} />
              </SelectTrigger>
              <SelectContent>
                {teams.map((team) => (
                  <SelectItem key={team.team_id} value={team.team_id}>
                    {team.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {!isLoading && teams.length === 0 ? (
              <p className="text-xs text-muted-foreground">
                暂无可共享的协作团队（已全部发布或你不属于任何协作团队）。
              </p>
            ) : null}
          </div>

          <div className="space-y-1.5">
            <Label>暴露别名（可选）</Label>
            <Input
              value={alias}
              onChange={(e) => {
                setAlias(e.target.value)
              }}
              placeholder={virtualModel}
              className="font-mono"
            />
          </div>
        </div>

        <DialogFooter>
          <Button
            variant="ghost"
            onClick={() => {
              onOpenChange(false)
            }}
          >
            取消
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={grantMutation.isPending || !teamId || teams.length === 0}
          >
            {grantMutation.isPending ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" /> : null}
            发布
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
