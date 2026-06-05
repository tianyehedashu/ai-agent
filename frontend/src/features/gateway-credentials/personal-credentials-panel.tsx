/**
 * 个人凭据（/my-credentials）列表与编辑，用于 AI Gateway 凭据页「个人」Tab。
 *
 * 新增动作由外层 [`pages/gateway/credentials.tsx`](../../pages/gateway/credentials.tsx)
 * 的 `CreateCredentialDialog` 统一承担，本组件仅承载列表渲染与编辑弹窗。
 */

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type React from 'react'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  gatewayApi,
  type GatewayCredentialUpdateBody,
  type ProviderCredential,
} from '@/api/gateway'
import type { GatewayTeam } from '@/api/gateway/teams'
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
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { PersonalCredentialBudgetInline } from '@/features/gateway-budget/personal-credential-budget-inline'
import { useGatewayBudgets } from '@/features/gateway-budget/use-gateway-budgets'
import { useInfinitePersonalModelPages } from '@/features/gateway-models/hooks/use-infinite-gateway-model-pages'
import { combineFetching } from '@/features/gateway-shared/combine-fetching'
import { GatewayRefreshButton } from '@/features/gateway-shared/gateway-refresh-button'
import { useGatewayTeamId } from '@/hooks/use-gateway-team-id'
import { useToast } from '@/hooks/use-toast'
import { lazyWithReload } from '@/lib/lazy-with-reload'
import { Key, Loader2, Pencil, Plus, Trash2, Upload } from '@/lib/lucide-icons'
import { useCurrentUser } from '@/stores/user'

import { USER_GATEWAY_CREDENTIAL_PROVIDER_IDS, credentialProviderLabel } from './constants'
import { CredentialDeleteConfirmDialog } from './credential-delete-confirm-dialog'
import { CredentialEditFields } from './credential-edit-fields'
import { invalidateCredentialProbeCache } from './credential-probe-cache'
import { useProviderProfilesCatalog } from './hooks/use-provider-profiles-catalog'
import { displayListApiKeyMasked } from './mask-display'
import { invalidateCredentialSummariesCache } from './use-credential-directory'
import { useCredentialEditForm } from './use-credential-edit-form'

const AddModelsDialog = lazyWithReload(() =>
  import('./add-models-dialog').then((m) => ({ default: m.AddModelsDialog }))
)

const ImportToTeamDialog = lazyWithReload(() =>
  import('./import-to-team-dialog').then((m) => ({ default: m.ImportToTeamDialog }))
)

export interface PersonalCredentialsPanelProps {
  /**
   * 上层接管「添加凭据」入口：可选预填 provider。
   * 若未注入，则 panel 不展示「添加账号」按钮。
   */
  onAddCredential?: (provider?: string) => void
  /** 可写入的协作团队列表，用于导入到团队对话框的目标团队选择。 */
  writableTeams?: GatewayTeam[]
}

export function PersonalCredentialsPanel({
  onAddCredential,
  writableTeams = [],
}: PersonalCredentialsPanelProps = {}): React.ReactElement {
  useProviderProfilesCatalog()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const currentUser = useCurrentUser()
  const hasAuthSession = currentUser !== null
  const teamId = useGatewayTeamId()
  const [editCred, setEditCred] = useState<ProviderCredential | null>(null)
  const [addModelsCred, setAddModelsCred] = useState<ProviderCredential | null>(null)
  const [credentialPendingDelete, setCredentialPendingDelete] = useState<ProviderCredential | null>(
    null
  )
  const [showFullMaskedInList, setShowFullMaskedInList] = useState(false)
  const [importDialogState, setImportDialogState] = useState<{
    open: boolean
    preselectedIds: string[]
  }>({ open: false, preselectedIds: [] })

  const {
    data: credentials = [],
    isLoading,
    isFetching,
    refetch: refetchCredentials,
  } = useQuery({
    queryKey: ['gateway', 'my-credentials'],
    queryFn: () => gatewayApi.listMyCredentials(),
    enabled: hasAuthSession,
  })
  const {
    data: personalBudgets = [],
    isFetching: budgetsFetching,
    refetch: refetchBudgets,
  } = useGatewayBudgets(teamId)
  const { items: myModels } = useInfinitePersonalModelPages(undefined, {
    enabled: hasAuthSession,
    prefetchMode: 'idle',
  })

  useEffect(() => {
    if (!hasAuthSession) {
      setShowFullMaskedInList(false)
    }
  }, [hasAuthSession])

  const byProvider = useMemo(() => {
    const m = new Map<string, ProviderCredential[]>()
    for (const c of credentials) {
      const list = m.get(c.provider) ?? []
      list.push(c)
      m.set(c.provider, list)
    }
    for (const [, list] of m) {
      list.sort((a, b) => a.name.localeCompare(b.name))
    }
    return m
  }, [credentials])

  const invalidate = useCallback((): void => {
    void queryClient.invalidateQueries({ queryKey: ['gateway', 'my-credentials'] })
    void queryClient.invalidateQueries({ queryKey: ['gateway', 'my-models'] })
    void queryClient.invalidateQueries({ queryKey: ['gateway', 'credentials'] })
    invalidateCredentialSummariesCache(queryClient)
  }, [queryClient])

  const handleRefresh = useCallback((): void => {
    void Promise.all([
      refetchCredentials(),
      refetchBudgets(),
      queryClient.invalidateQueries({ queryKey: ['gateway', 'my-models'] }),
    ])
  }, [queryClient, refetchBudgets, refetchCredentials])

  const isRefreshing = combineFetching(isFetching, budgetsFetching)

  const openEdit = useCallback((c: ProviderCredential): void => {
    setEditCred(c)
  }, [])

  const deleteMutation = useMutation({
    mutationFn: gatewayApi.deleteMyCredential,
    onSuccess: (_data, credentialId) => {
      invalidateCredentialProbeCache(queryClient, 'user', credentialId)
      invalidate()
      setCredentialPendingDelete(null)
      if (editCred?.id === credentialId) {
        setEditCred(null)
      }
      if (addModelsCred?.id === credentialId) {
        setAddModelsCred(null)
      }
      toast({ title: '凭据已删除', description: '关联的个人注册模型已一并移除' })
    },
    onError: (e: Error) => {
      setCredentialPendingDelete(null)
      toast({ variant: 'destructive', title: '删除失败', description: e.message })
    },
  })

  const pendingDeleteRef = useRef<ProviderCredential | null>(null)
  pendingDeleteRef.current = credentialPendingDelete

  const handleDeleteDialogOpenChange = useCallback((open: boolean) => {
    if (!open) setCredentialPendingDelete(null)
  }, [])

  const handleDeleteConfirm = useCallback(() => {
    const pending = pendingDeleteRef.current
    if (pending) {
      deleteMutation.mutate(pending.id)
    }
  }, [deleteMutation])

  const testMutation = useMutation({
    mutationFn: (credentialId: string) => gatewayApi.probeMyCredential(credentialId),
    onSuccess: (data) => {
      if (data.support !== 'error') toast({ title: 'Key 有效' })
      else {
        toast({
          variant: 'destructive',
          title: 'Key 验证失败',
          description: data.message ?? '上游探测失败',
        })
      }
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '验证失败', description: e.message })
    },
  })
  const { isPending: testIsPending, mutate: testMutate } = testMutation

  const outerClass = 'space-y-4'

  const providerSections = useMemo(
    () => (
      <>
        {USER_GATEWAY_CREDENTIAL_PROVIDER_IDS.map((provider) => {
          const rows = byProvider.get(provider) ?? []
          return (
            <section key={provider} className="rounded-lg border">
              <div className="flex flex-wrap items-center justify-between gap-2 bg-muted/30 px-4 py-2.5">
                <div className="flex items-center gap-2">
                  <Key className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm font-medium">{credentialProviderLabel(provider)}</span>
                  <Badge variant={rows.length > 0 ? 'secondary' : 'outline'}>
                    {rows.length > 0 ? rows.length : '—'}
                  </Badge>
                </div>
                <div className="flex items-center gap-1">
                  {rows.length > 0 ? (
                    <>
                      <Button
                        variant="ghost"
                        size="sm"
                        disabled={testIsPending}
                        onClick={() => {
                          const active = rows.find((row) => row.is_active) ?? rows[0]
                          testMutate(active.id)
                        }}
                      >
                        {testIsPending ? '验证中…' : '验证'}
                      </Button>
                      {writableTeams.length > 0 ? (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            setImportDialogState({
                              open: true,
                              preselectedIds: rows.map((r) => r.id),
                            })
                          }}
                        >
                          <Upload className="mr-1 h-3.5 w-3.5" />
                          导入到团队
                        </Button>
                      ) : null}
                    </>
                  ) : null}
                  {onAddCredential ? (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        onAddCredential(provider)
                      }}
                    >
                      <Plus className="mr-1 h-3.5 w-3.5" />
                      添加
                    </Button>
                  ) : null}
                </div>
              </div>
              {rows.length > 0 ? (
                <div className="divide-y">
                  {rows.map((c) => (
                    <div key={c.id}>
                      <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5 text-sm">
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="font-medium">{c.name}</span>
                            {!c.is_active ? (
                              <Badge variant="outline" className="text-[11px]">
                                已停用
                              </Badge>
                            ) : null}
                          </div>
                          <div className="mt-0.5 font-mono text-[11px] text-muted-foreground">
                            {displayListApiKeyMasked(showFullMaskedInList, true, c.api_key_masked)}
                          </div>
                          {c.api_base ? (
                            <span className="mt-0.5 block truncate text-[11px] text-muted-foreground">
                              {c.api_base}
                            </span>
                          ) : null}
                        </div>
                        <div className="flex gap-1">
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-8 px-2 text-xs"
                            onClick={() => {
                              setAddModelsCred(c)
                            }}
                          >
                            <Plus className="mr-1 h-3.5 w-3.5" />
                            模型
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => {
                              openEdit(c)
                            }}
                            aria-label="编辑"
                          >
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="text-destructive hover:text-destructive"
                            disabled={deleteMutation.isPending}
                            onClick={() => {
                              setCredentialPendingDelete(c)
                            }}
                            aria-label="删除凭据"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                      {currentUser?.id ? (
                        <div className="border-t bg-muted/10 px-4 py-2">
                          <p className="mb-1 text-[11px] text-muted-foreground">平台预算</p>
                          <PersonalCredentialBudgetInline
                            credentialId={c.id}
                            userId={currentUser.id}
                            budgets={personalBudgets}
                            myModels={myModels}
                          />
                        </div>
                      ) : null}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="px-4 py-8 text-center text-sm text-muted-foreground">暂无凭据</div>
              )}
            </section>
          )
        })}
      </>
    ),
    [
      showFullMaskedInList,
      byProvider,
      testIsPending,
      testMutate,
      openEdit,
      onAddCredential,
      setAddModelsCred,
      deleteMutation.isPending,
      currentUser?.id,
      personalBudgets,
      myModels,
      writableTeams.length,
    ]
  )

  if (!hasAuthSession) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 rounded-lg border py-12">
        <Key className="h-8 w-8 text-muted-foreground/60" />
        <p className="text-sm text-muted-foreground">请先登录以管理个人凭据</p>
      </div>
    )
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-12">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className={outerClass}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Label htmlFor="show-full-masked-list" className="cursor-pointer text-xs font-normal">
            显示掩码
          </Label>
          <Switch
            id="show-full-masked-list"
            checked={showFullMaskedInList}
            onCheckedChange={setShowFullMaskedInList}
            aria-label="在列表中显示完整 API Key 掩码"
          />
        </div>
        <div className="flex items-center gap-2">
          <GatewayRefreshButton
            isFetching={isRefreshing}
            ariaLabel="刷新个人凭据"
            onRefresh={handleRefresh}
          />
          {writableTeams.length > 0 && credentials.length > 0 ? (
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setImportDialogState({ open: true, preselectedIds: [] })
              }}
            >
              <Upload className="mr-1.5 h-4 w-4" />
              批量导入到团队
            </Button>
          ) : null}
          {onAddCredential ? (
            <Button
              size="sm"
              onClick={() => {
                onAddCredential()
              }}
            >
              <Plus className="mr-1.5 h-4 w-4" />
              添加账号
            </Button>
          ) : null}
        </div>
      </div>

      {providerSections}

      <Dialog
        open={editCred !== null}
        onOpenChange={(o) => {
          if (!o) setEditCred(null)
        }}
      >
        {editCred ? (
          <PersonalCredentialEditDialog
            key={editCred.id}
            cred={editCred}
            onClose={() => {
              setEditCred(null)
            }}
            onSaved={() => {
              invalidateCredentialProbeCache(queryClient, 'user', editCred.id)
              invalidate()
              setEditCred(null)
            }}
          />
        ) : null}
      </Dialog>

      <CredentialDeleteConfirmDialog
        credential={credentialPendingDelete}
        isPending={deleteMutation.isPending}
        variant="personal"
        onOpenChange={handleDeleteDialogOpenChange}
        onConfirm={handleDeleteConfirm}
      />

      {addModelsCred ? (
        <Suspense
          fallback={
            <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              加载添加模型…
            </div>
          }
        >
          <AddModelsDialog
            open
            onOpenChange={(next) => {
              if (!next) setAddModelsCred(null)
            }}
            scope="user"
            credentialId={addModelsCred.id}
            provider={addModelsCred.provider}
            credentialName={addModelsCred.name}
            isActive={addModelsCred.is_active}
            onEditPersonalCredential={() => {
              const target = addModelsCred
              setAddModelsCred(null)
              openEdit(target)
            }}
          />
        </Suspense>
      ) : null}

      <Suspense
        fallback={
          <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            加载导入…
          </div>
        }
      >
        <ImportToTeamDialog
          open={importDialogState.open}
          onOpenChange={(next) => {
            setImportDialogState((prev) => ({ ...prev, open: next }))
          }}
          preselectedCredentialIds={importDialogState.preselectedIds}
          credentials={credentials}
          writableTeams={writableTeams}
        />
      </Suspense>
    </div>
  )
}

function PersonalCredentialEditDialog({
  cred,
  onClose,
  onSaved,
}: Readonly<{
  cred: ProviderCredential
  onClose: () => void
  onSaved: () => void
}>): React.ReactElement {
  const { toast } = useToast()
  const form = useCredentialEditForm({ cred, trackIsActive: true })

  const revealFn = useCallback(() => gatewayApi.revealMyCredential(cred.id), [cred.id])

  const updateMutation = useMutation({
    mutationFn: (body: GatewayCredentialUpdateBody) => gatewayApi.updateMyCredential(cred.id, body),
    onSuccess: () => {
      toast({ title: '已保存' })
      onSaved()
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '保存失败', description: e.message })
    },
  })

  const handleSave = (): void => {
    if (!form.canSave) return
    updateMutation.mutate(form.buildUpdateBody())
  }

  return (
    <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-lg">
      <DialogHeader>
        <DialogTitle>编辑凭据</DialogTitle>
        <DialogDescription>
          修改账号名称、启用状态或密钥；默认显示掩码，需要时可查看完整明文，或点「更换」输入新密钥后保存。
        </DialogDescription>
      </DialogHeader>
      <div className="grid gap-3 py-2">
        <CredentialEditFields
          cred={cred}
          idPrefix="my-cred"
          form={form}
          showActiveSwitch
          revealFn={revealFn}
        />
      </div>
      <DialogFooter>
        <Button variant="outline" onClick={onClose}>
          取消
        </Button>
        <Button onClick={handleSave} disabled={updateMutation.isPending || !form.canSave}>
          {updateMutation.isPending ? '保存中…' : '保存'}
        </Button>
      </DialogFooter>
    </DialogContent>
  )
}
