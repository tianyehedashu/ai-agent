/**
 * 凭据 + 关联模型跨 scope 复制对话框（个人 / 团队双向）。
 * 由父级在 open 时条件挂载，关闭即卸载，无需 open 重置 effect。
 */

import { useCallback, useEffect, useMemo, useState } from 'react'
import type React from 'react'

import { useMutation, useQueryClient } from '@tanstack/react-query'

import {
  credentialsApi,
  type CopyCredentialsWithModelsBody,
  type ImportCredentialsWithModelsResponse,
  type ProviderCredential,
} from '@/api/gateway/credentials'
import type { GatewayTeam } from '@/api/gateway/teams'
import { Badge } from '@/components/ui/badge'
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
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { MY_CREDENTIALS_QUERY_KEY } from '@/features/gateway-credentials/query-keys'
import { useToast } from '@/hooks/use-toast'
import { CheckCircle2, Loader2 } from '@/lib/lucide-icons'

import { credentialProviderLabel } from './constants'
import { displayListApiKeyMasked } from './mask-display'
import { invalidateGatewayCredentialCaches } from './query-keys'

const PERSONAL_SOURCE = '__personal__' as const
const PERSONAL_DEST = '__personal_dest__' as const

type SourceKey = string
type DestKey = string

interface CopyMutationVars {
  sourceKey: SourceKey
  destKey: DestKey
  credentialIds: string[]
}

export interface CopyCredentialsDialogProps {
  onOpenChange: (open: boolean) => void
  preselectedCredentialIds?: string[]
  personalCredentials: readonly ProviderCredential[]
  /** management_access=full 的团队凭据（由父级统一列表提供，避免重复请求） */
  teamCredentials: readonly ProviderCredential[]
  teamCredentialsLoading?: boolean
  contributorTeams: GatewayTeam[]
  teamNameById: Map<string, string>
}

function isFullAccessCredential(credential: ProviderCredential): boolean {
  return credential.management_access !== 'metadata'
}

function sourceLabel(key: SourceKey, teamNameById: Map<string, string>): string {
  if (key === PERSONAL_SOURCE) return '个人'
  return teamNameById.get(key) ?? key.slice(0, 8)
}

function destLabel(key: DestKey, teamNameById: Map<string, string>): string {
  if (key === PERSONAL_DEST) return '个人'
  return teamNameById.get(key) ?? key.slice(0, 8)
}

function buildCopyBody(vars: CopyMutationVars): CopyCredentialsWithModelsBody {
  const { sourceKey, destKey, credentialIds } = vars
  const source: CopyCredentialsWithModelsBody['source'] =
    sourceKey === PERSONAL_SOURCE ? { kind: 'personal' } : { kind: 'team', team_id: sourceKey }
  const destination: CopyCredentialsWithModelsBody['destination'] =
    destKey === PERSONAL_DEST ? { kind: 'personal' } : { kind: 'team', team_id: destKey }
  return { credential_ids: credentialIds, source, destination }
}

function buildAvailableSourceKeys(
  personalCredentials: readonly ProviderCredential[],
  sourceTeamOptions: GatewayTeam[]
): SourceKey[] {
  const keys: SourceKey[] = []
  if (personalCredentials.length > 0) keys.push(PERSONAL_SOURCE)
  for (const team of sourceTeamOptions) keys.push(team.id)
  return keys
}

function buildDestinationOptions(sourceKey: SourceKey, contributorTeams: GatewayTeam[]): DestKey[] {
  const opts: DestKey[] = []
  if (sourceKey !== PERSONAL_SOURCE) opts.push(PERSONAL_DEST)
  for (const team of contributorTeams) {
    if (sourceKey !== PERSONAL_SOURCE && team.id === sourceKey) continue
    opts.push(team.id)
  }
  return opts
}

function filterSelectedIds(ids: Set<string>, allowed: ReadonlySet<string>): Set<string> {
  const next = new Set([...ids].filter((id) => allowed.has(id)))
  return next.size === ids.size ? ids : next
}

export function CopyCredentialsDialog({
  onOpenChange,
  preselectedCredentialIds = [],
  personalCredentials,
  teamCredentials,
  teamCredentialsLoading = false,
  contributorTeams,
  teamNameById,
}: CopyCredentialsDialogProps): React.ReactElement {
  const queryClient = useQueryClient()
  const { toast } = useToast()

  const copyableTeamCredentials = useMemo(
    () => teamCredentials.filter(isFullAccessCredential),
    [teamCredentials]
  )

  const sourceTeamOptions = useMemo(() => {
    const teamIds = new Set<string>()
    for (const cred of copyableTeamCredentials) {
      if (cred.tenant_id) teamIds.add(cred.tenant_id)
    }
    return contributorTeams.filter((t) => teamIds.has(t.id))
  }, [copyableTeamCredentials, contributorTeams])

  const availableSourceKeys = useMemo(
    () => buildAvailableSourceKeys(personalCredentials, sourceTeamOptions),
    [personalCredentials, sourceTeamOptions]
  )

  const [sourceKey, setSourceKey] = useState<SourceKey>(
    () => availableSourceKeys[0] ?? PERSONAL_SOURCE
  )
  const [destKey, setDestKey] = useState<DestKey>(() => {
    const initialSource = availableSourceKeys[0] ?? PERSONAL_SOURCE
    return buildDestinationOptions(initialSource, contributorTeams)[0] ?? ''
  })
  const [selectedIds, setSelectedIds] = useState<Set<string>>(
    () => new Set(preselectedCredentialIds)
  )
  const [result, setResult] = useState<ImportCredentialsWithModelsResponse | null>(null)
  const [directionLabel, setDirectionLabel] = useState('')

  const destinationOptions = useMemo(
    () => buildDestinationOptions(sourceKey, contributorTeams),
    [sourceKey, contributorTeams]
  )

  const sourceCredentials = useMemo(() => {
    if (sourceKey === PERSONAL_SOURCE) return personalCredentials
    return copyableTeamCredentials.filter((c) => c.tenant_id === sourceKey)
  }, [sourceKey, personalCredentials, copyableTeamCredentials])

  const allowedCredentialIds = useMemo(
    () => new Set(sourceCredentials.map((c) => c.id)),
    [sourceCredentials]
  )

  const copyMutation = useMutation({
    mutationFn: (vars: CopyMutationVars) =>
      credentialsApi.copyCredentialsWithModels(buildCopyBody(vars)),
    onSuccess: (data, vars) => {
      setResult(data)
      setDirectionLabel(
        `${sourceLabel(vars.sourceKey, teamNameById)} → ${destLabel(vars.destKey, teamNameById)}`
      )
      const destTeamId = vars.destKey === PERSONAL_DEST ? undefined : vars.destKey
      const sourceTeamId = vars.sourceKey === PERSONAL_SOURCE ? undefined : vars.sourceKey
      invalidateGatewayCredentialCaches(queryClient, { teamId: destTeamId, includeModels: true })
      if (sourceTeamId && sourceTeamId !== destTeamId) {
        invalidateGatewayCredentialCaches(queryClient, {
          teamId: sourceTeamId,
          includeModels: true,
        })
      }
      void queryClient.invalidateQueries({ queryKey: MY_CREDENTIALS_QUERY_KEY })
      const totalModels = data.succeeded.reduce((acc, s) => acc + s.models_created.length, 0)
      toast({
        title: '复制成功',
        description: `成功复制 ${String(data.succeeded.length)} 个凭据和 ${String(totalModels)} 个模型${data.failed.length > 0 ? `，${String(data.failed.length)} 个凭据失败` : ''}`,
      })
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '复制失败', description: e.message })
    },
  })

  // 异步数据到达后校正来源/目标；来源变更时清空非法选中项
  useEffect(() => {
    const nextSource = availableSourceKeys.includes(sourceKey)
      ? sourceKey
      : (availableSourceKeys[0] ?? PERSONAL_SOURCE)
    if (nextSource !== sourceKey) {
      setSourceKey(nextSource)
      setDestKey(buildDestinationOptions(nextSource, contributorTeams)[0] ?? '')
      setSelectedIds(new Set())
      return
    }
    const destOpts = buildDestinationOptions(nextSource, contributorTeams)
    if (!destKey || !destOpts.includes(destKey)) {
      setDestKey(destOpts[0] ?? '')
    }
  }, [availableSourceKeys, sourceKey, destKey, contributorTeams])

  useEffect(() => {
    setSelectedIds((prev) => filterSelectedIds(prev, allowedCredentialIds))
  }, [allowedCredentialIds])

  const byProvider = useMemo(() => {
    const map = new Map<string, ProviderCredential[]>()
    for (const c of sourceCredentials) {
      const list = map.get(c.provider) ?? []
      list.push(c)
      map.set(c.provider, list)
    }
    return map
  }, [sourceCredentials])

  const toggleCredential = useCallback((id: string): void => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [])

  const toggleProviderAll = useCallback((rows: ProviderCredential[]): void => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      const allSelected = rows.every((r) => next.has(r.id))
      for (const r of rows) {
        if (allSelected) next.delete(r.id)
        else next.add(r.id)
      }
      return next
    })
  }, [])

  const handleSourceChange = useCallback(
    (nextSource: SourceKey): void => {
      setSourceKey(nextSource)
      setDestKey(buildDestinationOptions(nextSource, contributorTeams)[0] ?? '')
      setSelectedIds(new Set())
    },
    [contributorTeams]
  )

  const handleCopy = useCallback((): void => {
    if (!destKey || selectedIds.size === 0) return
    copyMutation.mutate({
      sourceKey,
      destKey,
      credentialIds: Array.from(selectedIds),
    })
  }, [copyMutation, destKey, selectedIds, sourceKey])

  const showResult = result !== null
  const isCopying = copyMutation.isPending
  const canSubmit = selectedIds.size > 0 && destKey !== '' && !isCopying && !teamCredentialsLoading

  return (
    <Dialog
      open
      onOpenChange={(next) => {
        if (!next) onOpenChange(false)
      }}
    >
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>复制凭据和模型</DialogTitle>
          <DialogDescription>
            选择来源与目标。复制不会删除源凭据；关联的已注册模型将一并复制。
          </DialogDescription>
        </DialogHeader>

        {isCopying ? (
          <div className="flex flex-col items-center gap-3 py-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            <p className="text-sm text-muted-foreground">正在复制凭据和模型…</p>
          </div>
        ) : showResult ? (
          <div className="space-y-4">
            <div className="flex items-center gap-2 text-sm">
              <CheckCircle2 className="h-5 w-5 text-green-600" />
              <span className="font-medium">复制完成</span>
            </div>
            {directionLabel ? (
              <p className="text-xs text-muted-foreground">{directionLabel}</p>
            ) : null}
            {result.succeeded.length > 0 ? (
              <div className="space-y-2">
                <Label className="text-xs">成功复制</Label>
                <ul className="space-y-1">
                  {result.succeeded.map((s) => (
                    <li
                      key={s.source_credential_id}
                      className="rounded-md border px-3 py-2 text-sm"
                    >
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{s.new_credential.name}</span>
                        <Badge variant="secondary" className="text-[11px]">
                          {s.new_credential.provider}
                        </Badge>
                      </div>
                      <p className="mt-0.5 text-[11px] text-muted-foreground">
                        创建 {s.models_created.length} 个模型
                        {s.models_failed.length > 0
                          ? `，${String(s.models_failed.length)} 个模型失败`
                          : ''}
                      </p>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
            {result.failed.length > 0 ? (
              <div className="space-y-2">
                <Label className="text-xs text-destructive">失败</Label>
                <ul className="space-y-1">
                  {result.failed.map((f) => (
                    <li
                      key={f.credential_id}
                      className="rounded-md border border-destructive/30 px-3 py-2 text-sm"
                    >
                      <span className="font-mono text-[11px]">{f.credential_id}</span>
                      <p className="text-[11px] text-destructive">{f.reason}</p>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
        ) : (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>来源</Label>
              {availableSourceKeys.length === 0 ? (
                <p className="text-sm text-muted-foreground">暂无可复制的凭据</p>
              ) : (
                <Select value={sourceKey} onValueChange={handleSourceChange}>
                  <SelectTrigger>
                    <SelectValue placeholder="请选择来源" />
                  </SelectTrigger>
                  <SelectContent>
                    {availableSourceKeys.map((key) => (
                      <SelectItem key={key} value={key}>
                        {sourceLabel(key, teamNameById)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            </div>

            <div className="space-y-2">
              <Label>选择凭据</Label>
              {teamCredentialsLoading && sourceKey !== PERSONAL_SOURCE ? (
                <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  加载团队凭据…
                </div>
              ) : sourceCredentials.length === 0 ? (
                <p className="text-sm text-muted-foreground">该来源下暂无可复制凭据</p>
              ) : (
                <div className="space-y-3">
                  {Array.from(byProvider.entries()).map(([provider, rows]) => (
                    <div key={provider} className="rounded-md border">
                      <div className="flex items-center justify-between bg-muted/30 px-3 py-2">
                        <span className="text-sm font-medium">
                          {credentialProviderLabel(provider)}
                        </span>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-6 px-2 text-xs"
                          onClick={() => {
                            toggleProviderAll(rows)
                          }}
                        >
                          {rows.every((r) => selectedIds.has(r.id)) ? '取消全选' : '全选'}
                        </Button>
                      </div>
                      <div className="divide-y">
                        {rows.map((c) => (
                          <label
                            key={c.id}
                            className="flex cursor-pointer items-start gap-3 px-3 py-2"
                          >
                            <Checkbox
                              checked={selectedIds.has(c.id)}
                              onCheckedChange={() => {
                                toggleCredential(c.id)
                              }}
                              className="mt-0.5"
                            />
                            <div className="min-w-0 flex-1">
                              <div className="flex items-center gap-2">
                                <span className="text-sm font-medium">{c.name}</span>
                                {!c.is_active ? (
                                  <Badge variant="outline" className="text-[11px]">
                                    已停用
                                  </Badge>
                                ) : null}
                              </div>
                              <p className="mt-0.5 font-mono text-[11px] text-muted-foreground">
                                {displayListApiKeyMasked(
                                  sourceKey !== PERSONAL_SOURCE,
                                  c.management_access !== 'metadata',
                                  c.api_key_masked
                                )}
                              </p>
                            </div>
                          </label>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="space-y-2">
              <Label>目标</Label>
              {destinationOptions.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  暂无可用的目标。请先创建或加入一个协作团队。
                </p>
              ) : (
                <Select value={destKey} onValueChange={setDestKey}>
                  <SelectTrigger>
                    <SelectValue placeholder="请选择目标" />
                  </SelectTrigger>
                  <SelectContent>
                    {destinationOptions.map((key) => (
                      <SelectItem key={key} value={key}>
                        {destLabel(key, teamNameById)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            </div>
          </div>
        )}

        <DialogFooter>
          {showResult ? (
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
                variant="outline"
                disabled={isCopying}
                onClick={() => {
                  onOpenChange(false)
                }}
              >
                取消
              </Button>
              <Button onClick={handleCopy} disabled={!canSubmit}>
                {isCopying ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    复制中…
                  </>
                ) : (
                  `复制 ${String(selectedIds.size)} 个凭据`
                )}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
