/**
 * 凭据 + 关联模型跨 scope 复制对话框（个人 / 团队双向）。
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

type CopyStep = 'select' | 'copying' | 'result'

export interface CopyCredentialsDialogProps {
  open: boolean
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

function buildCopyBody(
  sourceKey: SourceKey,
  destKey: DestKey,
  credentialIds: string[]
): CopyCredentialsWithModelsBody {
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
  for (const team of sourceTeamOptions) {
    keys.push(team.id)
  }
  return keys
}

function buildDestinationOptions(sourceKey: SourceKey, contributorTeams: GatewayTeam[]): DestKey[] {
  const opts: DestKey[] = []
  if (sourceKey !== PERSONAL_SOURCE) {
    opts.push(PERSONAL_DEST)
  }
  for (const team of contributorTeams) {
    if (sourceKey !== PERSONAL_SOURCE && team.id === sourceKey) continue
    opts.push(team.id)
  }
  return opts
}

export function CopyCredentialsDialog({
  open,
  onOpenChange,
  preselectedCredentialIds,
  personalCredentials,
  teamCredentials,
  teamCredentialsLoading = false,
  contributorTeams,
  teamNameById,
}: CopyCredentialsDialogProps): React.ReactElement {
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [step, setStep] = useState<CopyStep>('select')
  const [sourceKey, setSourceKey] = useState<SourceKey>(PERSONAL_SOURCE)
  const [destKey, setDestKey] = useState<DestKey>('')
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [result, setResult] = useState<ImportCredentialsWithModelsResponse | null>(null)
  const [directionLabel, setDirectionLabel] = useState('')

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

  const destinationOptions = useMemo(
    () => buildDestinationOptions(sourceKey, contributorTeams),
    [sourceKey, contributorTeams]
  )

  const sourceCredentials = useMemo(() => {
    if (sourceKey === PERSONAL_SOURCE) return [...personalCredentials]
    return copyableTeamCredentials.filter((c) => c.tenant_id === sourceKey)
  }, [sourceKey, personalCredentials, copyableTeamCredentials])

  const copyMutation = useMutation({
    mutationFn: () => {
      if (!destKey) throw new Error('请选择目标')
      if (selectedIds.size === 0) throw new Error('请选择至少一个凭据')
      return credentialsApi.copyCredentialsWithModels(
        buildCopyBody(sourceKey, destKey, Array.from(selectedIds))
      )
    },
    onSuccess: (data) => {
      setResult(data)
      setDirectionLabel(
        `${sourceLabel(sourceKey, teamNameById)} → ${destLabel(destKey, teamNameById)}`
      )
      setStep('result')
      const destTeamId = destKey === PERSONAL_DEST ? undefined : destKey
      const sourceTeamId = sourceKey === PERSONAL_SOURCE ? undefined : sourceKey
      invalidateGatewayCredentialCaches(queryClient, {
        teamId: destTeamId,
        includeModels: true,
      })
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
      setStep('select')
    },
  })

  useEffect(() => {
    if (!open) return
    const nextSource =
      buildAvailableSourceKeys(personalCredentials, sourceTeamOptions)[0] ?? PERSONAL_SOURCE
    const nextDest = buildDestinationOptions(nextSource, contributorTeams)[0] ?? ''
    setStep('select')
    setSourceKey(nextSource)
    setDestKey(nextDest)
    setSelectedIds(new Set(preselectedCredentialIds ?? []))
    setResult(null)
    setDirectionLabel('')
    copyMutation.reset()
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reset when dialog opens
  }, [open, preselectedCredentialIds])

  useEffect(() => {
    if (!open) return
    if (!availableSourceKeys.includes(sourceKey)) {
      const nextSource = availableSourceKeys[0] ?? PERSONAL_SOURCE
      setSourceKey(nextSource)
      setDestKey(buildDestinationOptions(nextSource, contributorTeams)[0] ?? '')
      setSelectedIds(new Set())
    }
  }, [open, availableSourceKeys, sourceKey, contributorTeams])

  useEffect(() => {
    if (!open) return
    if (destKey === '' || !destinationOptions.includes(destKey)) {
      setDestKey(destinationOptions[0] ?? '')
    }
  }, [open, destinationOptions, destKey])

  useEffect(() => {
    if (!open) return
    const allowed = new Set(sourceCredentials.map((c) => c.id))
    setSelectedIds((prev) => {
      const next = new Set([...prev].filter((id) => allowed.has(id)))
      return next.size === prev.size ? prev : next
    })
  }, [open, sourceCredentials])

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

  const canSubmit =
    selectedIds.size > 0 && destKey !== '' && step === 'select' && !teamCredentialsLoading

  const handleCopy = useCallback((): void => {
    setStep('copying')
    copyMutation.mutate()
  }, [copyMutation])

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>复制凭据和模型</DialogTitle>
          <DialogDescription>
            选择来源与目标。复制不会删除源凭据；关联的已注册模型将一并复制。
          </DialogDescription>
        </DialogHeader>

        {step === 'select' ? (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>来源</Label>
              {availableSourceKeys.length === 0 ? (
                <p className="text-sm text-muted-foreground">暂无可复制的凭据</p>
              ) : (
                <Select
                  value={sourceKey}
                  onValueChange={(v) => {
                    const nextSource = v
                    setSourceKey(nextSource)
                    setDestKey(buildDestinationOptions(nextSource, contributorTeams)[0] ?? '')
                    setSelectedIds(new Set())
                  }}
                >
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
                <Select
                  value={destKey}
                  onValueChange={(v) => {
                    setDestKey(v)
                  }}
                >
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
        ) : step === 'copying' ? (
          <div className="flex flex-col items-center gap-3 py-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            <p className="text-sm text-muted-foreground">正在复制凭据和模型…</p>
          </div>
        ) : (
          <div className="space-y-4">
            {result ? (
              <>
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
                      {result.failed.map((f, i) => (
                        <li
                          key={i}
                          className="rounded-md border border-destructive/30 px-3 py-2 text-sm"
                        >
                          <span className="font-mono text-[11px]">{f.credential_id}</span>
                          <p className="text-[11px] text-destructive">{f.reason}</p>
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </>
            ) : null}
          </div>
        )}

        <DialogFooter>
          {step === 'result' ? (
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
                onClick={() => {
                  onOpenChange(false)
                }}
              >
                取消
              </Button>
              <Button onClick={handleCopy} disabled={!canSubmit}>
                {step === 'copying' ? (
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
