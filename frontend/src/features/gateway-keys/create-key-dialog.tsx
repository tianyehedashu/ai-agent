import { useEffect, useMemo, useState } from 'react'

import { Link } from 'react-router-dom'

import type { GatewayTeam } from '@/api/gateway/teams'
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
import { Switch } from '@/components/ui/switch'
import { GatewayTeamCombobox } from '@/features/gateway-teams/gateway-team-combobox'
import { gatewayWorkspaceLabel } from '@/features/gateway-teams/gateway-team-display'
import { useToast } from '@/hooks/use-toast'
import { Copy } from '@/lib/lucide-icons'
import { useUserStore } from '@/stores/user'

export interface CreateKeyValues {
  name: string
  store_full_messages: boolean
  rpm_limit?: number | null
  tpm_limit?: number | null
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
  const viewerUserId = useUserStore((s) => s.currentUser?.id ?? null)
  const [targetTeamId, setTargetTeamId] = useState('')
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

  useEffect(() => {
    if (!open || plaintext) return
    setTargetTeamId(resolveInitialTeamId(targetTeams, routeTeamId))
  }, [open, plaintext, routeTeamId, targetTeams])

  const canSubmit =
    values.name.trim().length > 0 && targetTeamId.length > 0 && targetTeams.length > 0

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
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
                onClick={() => {
                  void navigator.clipboard.writeText(plaintext)
                  toast({ title: '已复制' })
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
                    ，调用时无需再传团队头。
                  </p>
                  {crossWorkspaceTarget ? (
                    <p className="text-[11px] text-amber-700 dark:text-amber-400">
                      将创建到其他工作区，创建后可在本页列表中查看。
                    </p>
                  ) : null}
                </>
              )}
            </div>
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
                  onSubmit(targetTeamId, values)
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
