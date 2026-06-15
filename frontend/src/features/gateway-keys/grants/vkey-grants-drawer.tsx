/**
 * VKey Grants Drawer — 跨团队授权管理
 */

import { useCallback, useEffect, useMemo, useState } from 'react'

import type { GrantableTeam, VirtualKeyTeamGrant } from '@/api/gateway/grants'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { useToast } from '@/hooks/use-toast'
import { AlertTriangle, Check, Network, Plus, Trash2, X } from '@/lib/lucide-icons'

import { findHomonymModels } from './use-team-slug-map'
import { useGrantableTeams, useGrantMutations, useVkeyGrants } from './use-vkey-grants'

export interface VKeyGrantsDrawerProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  teamId: string
  vkeyId: string
  vkeyName: string
}

function GrantTeamModels({
  grant,
}: Readonly<{ grant: VirtualKeyTeamGrant }>): React.JSX.Element | null {
  const names = grant.registered_model_names ?? []
  if (names.length === 0) return null
  const preview = names.slice(0, 8).join(', ')
  const suffix = names.length > 8 ? ` … +${String(names.length - 8)}` : ''
  return (
    <p className="mt-1 truncate text-xs text-muted-foreground" title={names.join(', ')}>
      {preview}
      {suffix}
    </p>
  )
}

export function VKeyGrantsDrawer({
  open,
  onOpenChange,
  teamId,
  vkeyId,
  vkeyName,
}: Readonly<VKeyGrantsDrawerProps>): React.JSX.Element {
  const { toast } = useToast()
  const { data: grants = [], isLoading } = useVkeyGrants(teamId, vkeyId, open)
  const { data: grantableTeams = [] } = useGrantableTeams(teamId, vkeyId, open)
  const { addMutation, revokeMutation } = useGrantMutations(teamId, vkeyId)

  const [selectedToAdd, setSelectedToAdd] = useState<Set<string>>(new Set())
  const [addingMode, setAddingMode] = useState(false)
  const [teamFilter, setTeamFilter] = useState('')

  useEffect(() => {
    if (!open) {
      setAddingMode(false)
      setSelectedToAdd(new Set())
      setTeamFilter('')
    }
  }, [open])

  const selfGrant = useMemo(() => grants.find((g) => g.is_self), [grants])
  const crossGrants = useMemo(() => grants.filter((g) => !g.is_self), [grants])
  const homonymModels = useMemo(() => findHomonymModels(grants), [grants])

  const filteredGrantable = useMemo(() => {
    const q = teamFilter.trim().toLowerCase()
    if (!q) return grantableTeams
    return grantableTeams.filter(
      (t) => t.name.toLowerCase().includes(q) || t.slug.toLowerCase().includes(q)
    )
  }, [grantableTeams, teamFilter])

  const toggleAddSelection = useCallback((tenantId: string, checked: boolean): void => {
    setSelectedToAdd((prev) => {
      const next = new Set(prev)
      if (checked) next.add(tenantId)
      else next.delete(tenantId)
      return next
    })
  }, [])

  const handleAddConfirm = useCallback((): void => {
    if (selectedToAdd.size === 0) return
    addMutation.mutate([...selectedToAdd], {
      onSuccess: () => {
        setSelectedToAdd(new Set())
        setAddingMode(false)
        toast({ title: '授权成功' })
      },
      onError: (e: Error) => {
        toast({ variant: 'destructive', title: '授权失败', description: e.message })
      },
    })
  }, [addMutation, selectedToAdd, toast])

  const handleRevoke = useCallback(
    (tenantId: string): void => {
      revokeMutation.mutate(tenantId, {
        onSuccess: () => {
          toast({ title: '已撤销授权' })
        },
        onError: (e: Error) => {
          toast({ variant: 'destructive', title: '撤销失败', description: e.message })
        },
      })
    },
    [revokeMutation, toast]
  )

  const homonymBanner =
    homonymModels.length > 0 ? (
      <Alert variant="default" className="border-amber-500/40 bg-amber-500/5">
        <AlertTriangle className="h-4 w-4 text-amber-600" />
        <AlertTitle className="text-sm">存在跨 team 同名模型</AlertTitle>
        <AlertDescription className="text-xs">
          {homonymModels.map((name) => (
            <span key={name} className="mr-2 inline-block">
              <code className="rounded bg-muted px-1">{name}</code>
            </span>
          ))}
          请使用 <code className="rounded bg-muted px-1">team-slug/model-name</code> 显式指定目标
          team，避免无前缀调用落到个人。
        </AlertDescription>
      </Alert>
    ) : null

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="sm:max-w-md">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            <Network className="h-5 w-5" />
            跨团队授权
          </SheetTitle>
          <SheetDescription>
            管理「{vkeyName}」可访问的 team 模型。调用时使用{' '}
            <code className="rounded bg-muted px-1 text-xs">team-slug/model-name</code> 前缀指定目标
            team。
          </SheetDescription>
        </SheetHeader>

        <div className="mt-6 space-y-6">
          {homonymBanner}

          <section>
            <h4 className="mb-2 text-xs font-semibold uppercase text-muted-foreground">个人</h4>
            {isLoading ? (
              <p className="text-sm text-muted-foreground">加载中…</p>
            ) : selfGrant ? (
              <div className="rounded-md border px-3 py-2">
                <div className="flex items-center justify-between gap-2">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">
                      {selfGrant.granted_team_name ?? selfGrant.tenant_id.slice(0, 8)}
                    </p>
                    <p className="truncate font-mono text-xs text-muted-foreground">
                      {selfGrant.granted_team_slug ?? '—'}
                    </p>
                  </div>
                  <Badge variant="secondary" className="shrink-0 text-xs">
                    个人 · {selfGrant.model_count ?? 0} 模型
                  </Badge>
                </div>
                <GrantTeamModels grant={selfGrant} />
              </div>
            ) : null}
          </section>

          <section>
            <div className="mb-2 flex items-center justify-between">
              <h4 className="text-xs font-semibold uppercase text-muted-foreground">
                跨团队授权（{crossGrants.length}）
              </h4>
              {grantableTeams.length > 0 ? (
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7"
                  onClick={() => {
                    setAddingMode((v) => !v)
                    setSelectedToAdd(new Set())
                  }}
                >
                  {addingMode ? (
                    <>
                      <X className="mr-1 h-3.5 w-3.5" />
                      取消
                    </>
                  ) : (
                    <>
                      <Plus className="mr-1 h-3.5 w-3.5" />
                      添加授权
                    </>
                  )}
                </Button>
              ) : null}
            </div>

            {crossGrants.length === 0 && !addingMode ? (
              <p className="py-4 text-center text-sm text-muted-foreground">
                尚无跨团队授权。使用此 Key 只能访问个人的模型。
              </p>
            ) : (
              <ul className="space-y-1.5">
                {crossGrants.map((g) => (
                  <li key={g.id} className="rounded-md border px-3 py-2">
                    <div className="flex items-center justify-between gap-2">
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium">
                          {g.granted_team_name ?? g.tenant_id.slice(0, 8)}
                        </p>
                        <p className="truncate font-mono text-xs text-muted-foreground">
                          {g.granted_team_slug ?? g.tenant_id.slice(0, 12)}
                          {' · '}
                          {g.model_count ?? 0} 模型
                        </p>
                        <GrantTeamModels grant={g} />
                      </div>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 shrink-0"
                        aria-label={`撤销 ${g.granted_team_name ?? g.tenant_id.slice(0, 8)} 的授权`}
                        onClick={() => {
                          handleRevoke(g.tenant_id)
                        }}
                      >
                        <Trash2 className="h-3.5 w-3.5 text-destructive" />
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
            )}

            {addingMode ? (
              <div className="mt-3 space-y-2">
                <p className="text-xs text-muted-foreground">
                  选择要授权的工作区（默认不勾选，按需逐个选择）：
                </p>
                {grantableTeams.length > 10 ? (
                  <Input
                    placeholder="搜索工作区名称或 slug…"
                    value={teamFilter}
                    onChange={(e) => {
                      setTeamFilter(e.target.value)
                    }}
                    className="h-8 text-sm"
                  />
                ) : null}
                {filteredGrantable.length === 0 ? (
                  <p className="py-2 text-center text-sm text-muted-foreground">
                    没有更多可授权的工作区
                  </p>
                ) : (
                  <ul className="max-h-64 space-y-1.5 overflow-y-auto">
                    {filteredGrantable.map((t) => (
                      <GrantableTeamRow
                        key={t.team_id}
                        team={t}
                        checked={selectedToAdd.has(t.team_id)}
                        onToggle={toggleAddSelection}
                      />
                    ))}
                  </ul>
                )}
                <div className="flex justify-end gap-2 pt-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setAddingMode(false)
                      setSelectedToAdd(new Set())
                    }}
                  >
                    取消
                  </Button>
                  <Button
                    size="sm"
                    disabled={selectedToAdd.size === 0 || addMutation.isPending}
                    onClick={handleAddConfirm}
                  >
                    {addMutation.isPending ? (
                      '授权中…'
                    ) : (
                      <>
                        <Check className="mr-1 h-3.5 w-3.5" />
                        确认授权（{selectedToAdd.size}）
                      </>
                    )}
                  </Button>
                </div>
              </div>
            ) : null}
          </section>

          <section className="rounded-md bg-muted/50 p-3">
            <h4 className="mb-1 text-xs font-semibold text-muted-foreground">调用方式</h4>
            <pre className="mt-1.5 overflow-x-auto rounded bg-background p-2 text-xs">{`{
  "model": "my-team/gpt-4o",
  "messages": [...]
}`}</pre>
          </section>
        </div>
      </SheetContent>
    </Sheet>
  )
}

function GrantableTeamRow({
  team,
  checked,
  onToggle,
}: Readonly<{
  team: GrantableTeam
  checked: boolean
  onToggle: (tenantId: string, checked: boolean) => void
}>): React.JSX.Element {
  return (
    <li className="flex items-center gap-3 rounded-md border px-3 py-2">
      <Checkbox
        checked={checked}
        onCheckedChange={(v) => {
          onToggle(team.team_id, v === true)
        }}
      />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{team.name}</p>
        <p className="truncate text-xs text-muted-foreground">
          <span className="font-mono">{team.slug}</span>
          {' · '}
          {team.model_count ?? 0} 模型
        </p>
      </div>
    </li>
  )
}
