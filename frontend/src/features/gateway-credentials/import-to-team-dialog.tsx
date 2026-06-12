/**
 * 个人凭据 + 关联模型导入到团队对话框
 *
 * 用户选择要导入的个人凭据，选择目标团队，一键复制凭据和已注册模型到团队。
 */

import { useCallback, useMemo, useState } from 'react'
import type React from 'react'

import { useMutation, useQueryClient } from '@tanstack/react-query'

import {
  credentialsApi,
  type ImportCredentialsWithModelsResponse,
  type ProviderCredential,
} from '@/api/gateway'
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
import { useToast } from '@/hooks/use-toast'
import { CheckCircle2, Loader2 } from '@/lib/lucide-icons'

import { credentialProviderLabel } from './constants'
import { displayListApiKeyMasked } from './mask-display'
import { invalidateGatewayCredentialCaches } from './query-keys'

export interface ImportToTeamDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** 预选的凭据 ID 列表（从某个 provider section 进入时预选） */
  preselectedCredentialIds?: string[]
  /** 当前用户的全部个人凭据 */
  credentials: ProviderCredential[]
  /** 可选目标团队（排除 personal） */
  writableTeams: GatewayTeam[]
}

type ImportStep = 'select' | 'importing' | 'result'

export function ImportToTeamDialog({
  open,
  onOpenChange,
  preselectedCredentialIds,
  credentials,
  writableTeams,
}: ImportToTeamDialogProps): React.ReactElement {
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [step, setStep] = useState<ImportStep>('select')
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [targetTeamId, setTargetTeamId] = useState('')
  const [result, setResult] = useState<ImportCredentialsWithModelsResponse | null>(null)

  // Reset state when dialog opens
  const handleOpenChange = useCallback(
    (nextOpen: boolean): void => {
      if (nextOpen) {
        setStep('select')
        setSelectedIds(new Set(preselectedCredentialIds ?? []))
        setTargetTeamId('')
        setResult(null)
      }
      onOpenChange(nextOpen)
    },
    [onOpenChange, preselectedCredentialIds]
  )

  // Group credentials by provider
  const byProvider = useMemo(() => {
    const map = new Map<string, ProviderCredential[]>()
    for (const c of credentials) {
      const list = map.get(c.provider) ?? []
      list.push(c)
      map.set(c.provider, list)
    }
    return map
  }, [credentials])

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

  const importMutation = useMutation({
    mutationFn: () => {
      if (!targetTeamId) throw new Error('请选择目标团队')
      if (selectedIds.size === 0) throw new Error('请选择至少一个凭据')
      return credentialsApi.importCredentialsWithModels(targetTeamId, {
        credential_ids: Array.from(selectedIds),
      })
    },
    onSuccess: (data) => {
      setResult(data)
      setStep('result')
      invalidateGatewayCredentialCaches(queryClient, {
        teamId: targetTeamId,
        includeModels: true,
      })
      const totalModels = data.succeeded.reduce((acc, s) => acc + s.models_created.length, 0)
      toast({
        title: '导入成功',
        description: `成功导入 ${String(data.succeeded.length)} 个凭据和 ${String(totalModels)} 个模型${data.failed.length > 0 ? `，${String(data.failed.length)} 个凭据失败` : ''}`,
      })
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '导入失败', description: e.message })
      setStep('select')
    },
  })

  // Exclude personal team from target list
  const nonPersonalTeams = useMemo(
    () => writableTeams.filter((t) => t.kind !== 'personal'),
    [writableTeams]
  )

  const canSubmit = selectedIds.size > 0 && targetTeamId !== '' && step === 'select'

  const handleImport = useCallback((): void => {
    setStep('importing')
    importMutation.mutate()
  }, [importMutation])

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>导入凭据和模型到团队</DialogTitle>
          <DialogDescription>
            选择要导入的个人凭据和目标团队。凭据和其关联的已注册模型将一并复制到团队。
          </DialogDescription>
        </DialogHeader>

        {step === 'select' ? (
          <div className="space-y-4">
            {/* Credential selection */}
            <div className="space-y-2">
              <Label>选择凭据</Label>
              {credentials.length === 0 ? (
                <p className="text-sm text-muted-foreground">暂无个人凭据</p>
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
                                {displayListApiKeyMasked(false, true, c.api_key_masked)}
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

            {/* Team selector */}
            <div className="space-y-2">
              <Label>目标团队</Label>
              {nonPersonalTeams.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  暂无可用的协作团队。请先创建或加入一个团队。
                </p>
              ) : (
                <Select value={targetTeamId} onValueChange={setTargetTeamId}>
                  <SelectTrigger>
                    <SelectValue placeholder="请选择目标团队" />
                  </SelectTrigger>
                  <SelectContent>
                    {nonPersonalTeams.map((t) => (
                      <SelectItem key={t.id} value={t.id}>
                        {t.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            </div>
          </div>
        ) : step === 'importing' ? (
          <div className="flex flex-col items-center gap-3 py-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            <p className="text-sm text-muted-foreground">正在导入凭据和模型…</p>
          </div>
        ) : (
          /* Result */
          <div className="space-y-4">
            {result ? (
              <>
                <div className="flex items-center gap-2 text-sm">
                  <CheckCircle2 className="h-5 w-5 text-green-600" />
                  <span className="font-medium">导入完成</span>
                </div>
                {result.succeeded.length > 0 ? (
                  <div className="space-y-2">
                    <Label className="text-xs">成功导入</Label>
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
                          <span className="font-mono text-[11px]">{f.upstream_model_id}</span>
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
                handleOpenChange(false)
              }}
            >
              完成
            </Button>
          ) : (
            <>
              <Button
                variant="outline"
                onClick={() => {
                  handleOpenChange(false)
                }}
              >
                取消
              </Button>
              <Button onClick={handleImport} disabled={!canSubmit}>
                {step === 'importing' ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    导入中…
                  </>
                ) : (
                  `导入 ${String(selectedIds.size)} 个凭据`
                )}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
