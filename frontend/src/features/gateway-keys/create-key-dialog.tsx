import { useEffect, useMemo, useState } from 'react'

import { Link } from 'react-router-dom'

import type { GatewayTeam } from '@/api/gateway/teams'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
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
import { Switch } from '@/components/ui/switch'
import { GatewayTeamCombobox } from '@/features/gateway-teams/gateway-team-combobox'
import { gatewayWorkspaceLabel } from '@/features/gateway-teams/gateway-team-display'
import { useToast } from '@/hooks/use-toast'
import { Copy } from '@/lib/lucide-icons'
import { copyToClipboard } from '@/lib/utils'
import { useCurrentUser } from '@/stores/user'

export interface CreateKeyValues {
  name: string
  store_full_messages: boolean
  rpm_limit?: number | null
  tpm_limit?: number | null
  granted_team_ids?: string[]
}

/** 创建 vkey 时可勾选的跨团队 grant 候选（排除主属 team）。 */
export function grantableCrossTeams(
  teams: readonly GatewayTeam[],
  boundTeamId: string
): GatewayTeam[] {
  return teams.filter((team) => team.id !== boundTeamId)
}

function resolveInitialTeamId(
  targetTeams: readonly GatewayTeam[],
  defaultTeamId: string | undefined
): string {
  if (defaultTeamId && targetTeams.some((team) => team.id === defaultTeamId)) {
    return defaultTeamId
  }
  return targetTeams[0]?.id ?? ''
}

export interface CreateKeyDialogProps {
  open: boolean
  routeTeamId: string
  targetTeams: readonly GatewayTeam[]
  onOpenChange: (open: boolean) => void
  onSubmit: (targetTeamId: string, values: CreateKeyValues) => void
  plaintext: string | null
  createdKeyId: string | null
}

export function CreateKeyDialog({
  open,
  routeTeamId,
  targetTeams,
  onOpenChange,
  onSubmit,
  plaintext,
  createdKeyId,
}: Readonly<CreateKeyDialogProps>): React.JSX.Element {
  const viewerUserId = useCurrentUser()?.id ?? null
  const [targetTeamId, setTargetTeamId] = useState('')
  const [grantTeamFilter, setGrantTeamFilter] = useState('')
  const [selectedGrantTeamIds, setSelectedGrantTeamIds] = useState<Set<string>>(() => new Set())
  const [values, setValues] = useState<CreateKeyValues>({
    name: '',
    store_full_messages: false,
  })
  const { toast } = useToast()

  const labelForTeam = useMemo(
    () => (team: GatewayTeam) => gatewayWorkspaceLabel(team, { viewerUserId }),
    [viewerUserId]
  )

  const selectedTeam = useMemo(
    () => targetTeams.find((team) => team.id === targetTeamId) ?? null,
    [targetTeams, targetTeamId]
  )
  const workspaceLabel = selectedTeam ? gatewayWorkspaceLabel(selectedTeam, { viewerUserId }) : '—'
  const crossWorkspaceTarget =
    targetTeamId.length > 0 && routeTeamId.length > 0 && targetTeamId !== routeTeamId

  const grantableTeams = useMemo(
    () => grantableCrossTeams(targetTeams, targetTeamId),
    [targetTeams, targetTeamId]
  )

  const filteredGrantableTeams = useMemo(() => {
    const q = grantTeamFilter.trim().toLowerCase()
    if (!q) return grantableTeams
    return grantableTeams.filter(
      (team) =>
        team.name.toLowerCase().includes(q) ||
        team.slug.toLowerCase().includes(q) ||
        labelForTeam(team).toLowerCase().includes(q)
    )
  }, [grantableTeams, grantTeamFilter, labelForTeam])

  useEffect(() => {
    if (!open || plaintext) return
    setTargetTeamId(resolveInitialTeamId(targetTeams, routeTeamId))
    setSelectedGrantTeamIds(new Set())
    setGrantTeamFilter('')
  }, [open, plaintext, routeTeamId, targetTeams])

  useEffect(() => {
    if (!targetTeamId) return
    setSelectedGrantTeamIds((prev) => {
      if (!prev.has(targetTeamId)) return prev
      const next = new Set(prev)
      next.delete(targetTeamId)
      return next
    })
  }, [targetTeamId])

  const toggleGrantTeam = (teamId: string, checked: boolean): void => {
    setSelectedGrantTeamIds((prev) => {
      const next = new Set(prev)
      if (checked) next.add(teamId)
      else next.delete(teamId)
      return next
    })
  }

  const canSubmit =
    values.name.trim().length > 0 && targetTeamId.length > 0 && targetTeams.length > 0

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[min(90vh,720px)] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>创建虚拟 Key</DialogTitle>
          <DialogDescription>
            创建后请立即复制保存；之后仍可在列表中通过「查看」再次获取完整 Key。
          </DialogDescription>
        </DialogHeader>
        {plaintext ? (
          <div className="space-y-3 py-2">
            <Label className="text-xs text-muted-foreground">明文 Key（仅本次显示）</Label>
            <div className="flex items-center gap-2">
              <Input readOnly value={plaintext} className="font-mono text-xs" />
              <Button
                size="icon"
                variant="outline"
                onClick={async () => {
                  try {
                    await copyToClipboard(plaintext)
                    toast({ title: '已复制' })
                  } catch {
                    toast({ title: '复制失败，请手动选择文本复制', variant: 'destructive' })
                  }
                }}
              >
                <Copy className="h-4 w-4" />
              </Button>
            </div>
            {createdKeyId ? (
              <Button variant="outline" className="w-full" asChild>
                <Link
                  to={`/gateway/guide?key_id=${createdKeyId}#clients`}
                  state={{ vkeyPlain: plaintext, vkeyId: createdKeyId }}
                >
                  打开调用指南
                </Link>
              </Button>
            ) : null}
          </div>
        ) : (
          <div className="space-y-3 py-2">
            <div className="space-y-2">
              <Label htmlFor="key-target-workspace">绑定工作区</Label>
              <GatewayTeamCombobox
                id="key-target-workspace"
                value={targetTeamId}
                onChange={setTargetTeamId}
                teams={targetTeams}
                disabled={targetTeams.length === 0}
                placeholder={targetTeams.length === 0 ? '无可绑定的工作区' : '选择工作区'}
                labelForTeam={labelForTeam}
              />
              {targetTeams.length === 0 ? (
                <p className="text-[11px] text-destructive">
                  当前账号没有可创建虚拟 Key 的工作区。
                </p>
              ) : (
                <>
                  <p className="text-[11px] text-muted-foreground">
                    Key 将绑定到{' '}
                    <span className="font-medium text-foreground">{workspaceLabel}</span>
                    {selectedTeam?.kind === 'personal' ? '（个人）' : ''}
                    ；无前缀调用走{selectedTeam?.kind === 'personal' ? '个人' : '该工作区'}。
                  </p>
                  {crossWorkspaceTarget ? (
                    <p className="text-[11px] text-amber-700 dark:text-amber-400">
                      将创建到其他工作区，创建后可在本页列表中查看。
                    </p>
                  ) : null}
                </>
              )}
            </div>

            {grantableTeams.length > 0 ? (
              <div className="space-y-2 rounded-md border border-dashed p-3">
                <Label>跨工作区授权（可选）</Label>
                <p className="text-[11px] text-muted-foreground">
                  勾选后 Key 可同时访问其他工作区模型；跨 team 调用须带{' '}
                  <code className="rounded bg-muted px-1">team-slug/model-name</code> 前缀。
                </p>
                {grantableTeams.length > 10 ? (
                  <Input
                    placeholder="搜索工作区名称或 slug…"
                    value={grantTeamFilter}
                    onChange={(e) => {
                      setGrantTeamFilter(e.target.value)
                    }}
                    className="h-8 text-sm"
                  />
                ) : null}
                {filteredGrantableTeams.length === 0 ? (
                  <p className="py-2 text-center text-xs text-muted-foreground">无匹配工作区</p>
                ) : (
                  <ul className="max-h-40 space-y-1.5 overflow-y-auto">
                    {filteredGrantableTeams.map((team) => (
                      <li
                        key={team.id}
                        className="flex items-center gap-3 rounded-md border px-3 py-2"
                      >
                        <Checkbox
                          checked={selectedGrantTeamIds.has(team.id)}
                          onCheckedChange={(v) => {
                            toggleGrantTeam(team.id, v === true)
                          }}
                        />
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-medium">{labelForTeam(team)}</p>
                          <p className="truncate font-mono text-xs text-muted-foreground">
                            {team.slug}
                          </p>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
                {selectedGrantTeamIds.size > 0 ? (
                  <p className="text-[11px] text-muted-foreground">
                    已选 {selectedGrantTeamIds.size} 个额外工作区
                  </p>
                ) : null}
              </div>
            ) : null}

            <div>
              <Label htmlFor="key-name">名称</Label>
              <Input
                id="key-name"
                placeholder="生产环境 / SDK 客户端 / ..."
                value={values.name}
                onChange={(e) => {
                  setValues({ ...values, name: e.target.value })
                }}
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label htmlFor="rpm">每分钟请求数上限（留空不限）</Label>
                <Input
                  id="rpm"
                  type="number"
                  value={values.rpm_limit ?? ''}
                  onChange={(e) => {
                    setValues({
                      ...values,
                      rpm_limit: e.target.value ? Number(e.target.value) : null,
                    })
                  }}
                />
              </div>
              <div>
                <Label htmlFor="tpm">每分钟令牌数上限（留空不限）</Label>
                <Input
                  id="tpm"
                  type="number"
                  value={values.tpm_limit ?? ''}
                  onChange={(e) => {
                    setValues({
                      ...values,
                      tpm_limit: e.target.value ? Number(e.target.value) : null,
                    })
                  }}
                />
              </div>
            </div>
            <div className="flex items-center justify-between">
              <Label htmlFor="store" className="flex flex-col gap-1">
                <span>记录完整消息</span>
                <span className="text-xs text-muted-foreground">
                  关闭后仅存元数据（用于合规场景）
                </span>
              </Label>
              <Switch
                id="store"
                checked={values.store_full_messages}
                onCheckedChange={(v) => {
                  setValues({ ...values, store_full_messages: v })
                }}
              />
            </div>
          </div>
        )}
        <DialogFooter>
          {plaintext ? (
            <Button
              onClick={() => {
                onOpenChange(false)
              }}
            >
              完成
            </Button>
          ) : (
            <>
              <Button
                variant="ghost"
                onClick={() => {
                  onOpenChange(false)
                }}
              >
                取消
              </Button>
              <Button
                onClick={() => {
                  if (!canSubmit) return
                  const granted_team_ids =
                    selectedGrantTeamIds.size > 0 ? [...selectedGrantTeamIds] : undefined
                  onSubmit(targetTeamId, { ...values, granted_team_ids })
                }}
                disabled={!canSubmit}
              >
                创建
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
