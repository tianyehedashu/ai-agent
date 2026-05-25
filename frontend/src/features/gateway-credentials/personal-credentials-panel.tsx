/**
 * 个人凭据（/my-credentials）列表与编辑，用于 AI Gateway 凭据页「个人」Tab。
 *
 * 新增动作由外层 [`pages/gateway/credentials.tsx`](../../pages/gateway/credentials.tsx)
 * 的 `CreateCredentialDialog` 统一承担，本组件仅承载列表渲染与编辑弹窗。
 */

import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from 'react'
import type React from 'react'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  gatewayApi,
  type GatewayCredentialUpdateBody,
  type ProviderCredential,
} from '@/api/gateway'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
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
import { useGatewayTeamId } from '@/hooks/use-gateway-team-id'
import { useToast } from '@/hooks/use-toast'
import { Key, Loader2, Pencil, Plus, Trash2 } from '@/lib/lucide-icons'
import { useAuthStore } from '@/stores/auth'
import { useUserStore } from '@/stores/user'

import { USER_GATEWAY_CREDENTIAL_PROVIDER_IDS, credentialProviderLabel } from './constants'
import { CredentialEditFields } from './credential-edit-fields'
import { invalidateCredentialProbeCache } from './credential-probe-cache'
import { displayListApiKeyMasked } from './mask-display'
import { invalidateCredentialSummariesCache } from './use-credential-directory'
import { useCredentialEditForm } from './use-credential-edit-form'

const AddModelsDialog = lazy(() =>
  import('./add-models-dialog').then((m) => ({ default: m.AddModelsDialog }))
)

export interface PersonalCredentialsPanelProps {
  /**
   * 上层接管「添加凭据」入口：可选预填 provider。
   * 若未注入，则 panel 不展示「添加账号」按钮。
   */
  onAddCredential?: (provider?: string) => void
}

export function PersonalCredentialsPanel({
  onAddCredential,
}: PersonalCredentialsPanelProps = {}): React.ReactElement {
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const token = useAuthStore((s) => s.token)
  const hasAuthSession = Boolean(token)
  const teamId = useGatewayTeamId()
  const { currentUser } = useUserStore()
  const [editCred, setEditCred] = useState<ProviderCredential | null>(null)
  const [addModelsCred, setAddModelsCred] = useState<ProviderCredential | null>(null)
  const [credentialPendingDelete, setCredentialPendingDelete] = useState<ProviderCredential | null>(
    null
  )
  const [showFullMaskedInList, setShowFullMaskedInList] = useState(false)

  const { data: credentials = [], isLoading } = useQuery({
    queryKey: ['gateway', 'my-credentials'],
    queryFn: () => gatewayApi.listMyCredentials(),
    enabled: hasAuthSession,
  })
  const { data: personalBudgets = [] } = useGatewayBudgets(teamId)
  const { data: myModels = [] } = useQuery({
    queryKey: ['gateway', 'my-models'],
    queryFn: () => gatewayApi.listMyModels(),
    enabled: hasAuthSession,
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

  const credentialsBody = useMemo(
    () => (
      <>
        {hasAuthSession ? (
          <div className="flex flex-wrap items-center justify-end gap-2 border-b pb-3">
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
        ) : (
          <p className="text-sm text-muted-foreground">请先登录</p>
        )}
        {USER_GATEWAY_CREDENTIAL_PROVIDER_IDS.map((provider) => {
          const rows = byProvider.get(provider) ?? []
          return (
            <div key={provider} className="flex flex-col gap-3 rounded-lg border p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex min-w-0 items-center gap-2">
                  <Key className="h-4 w-4 shrink-0 text-muted-foreground" />
                  <span className="font-medium">{credentialProviderLabel(provider)}</span>
                  <Badge variant={rows.length > 0 ? 'secondary' : 'outline'}>
                    {rows.length > 0 ? rows.length : '—'}
                  </Badge>
                </div>
                <div className="flex flex-wrap gap-2">
                  {onAddCredential ? (
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={!hasAuthSession}
                      onClick={() => {
                        onAddCredential(provider)
                      }}
                    >
                      添加账号
                    </Button>
                  ) : null}
                  {rows.length > 0 ? (
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={!hasAuthSession || testIsPending}
                      onClick={() => {
                        const active = rows.find((row) => row.is_active) ?? rows[0]
                        testMutate(active.id)
                      }}
                    >
                      {testIsPending ? '验证中…' : '验证'}
                    </Button>
                  ) : null}
                </div>
              </div>
              {rows.length > 0 ? (
                <ul className="divide-y rounded-md border">
                  {rows.map((c) => (
                    <li key={c.id} className="border-b last:border-0">
                      <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 text-sm">
                        <div className="min-w-0 flex-1">
                          <span className="font-medium">{c.name}</span>
                          <div className="mt-0.5 font-mono text-[11px] text-muted-foreground">
                            {displayListApiKeyMasked(
                              showFullMaskedInList,
                              hasAuthSession,
                              c.api_key_masked
                            )}
                          </div>
                          {c.api_base ? (
                            <span className="mt-0.5 block truncate text-muted-foreground">
                              {c.api_base}
                            </span>
                          ) : null}
                          {!c.is_active ? (
                            <Badge variant="outline" className="ml-2">
                              已停用
                            </Badge>
                          ) : null}
                        </div>
                        <div className="flex gap-1">
                          {hasAuthSession ? (
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
                          ) : null}
                          <Button
                            variant="ghost"
                            size="icon"
                            disabled={!hasAuthSession}
                            onClick={() => {
                              openEdit(c)
                            }}
                            aria-label="编辑"
                          >
                            <Pencil className="h-4 w-4" />
                          </Button>
                          {hasAuthSession ? (
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
                          ) : null}
                        </div>
                      </div>
                      {currentUser?.id ? (
                        <div className="border-t bg-muted/10 px-3 py-2">
                          <p className="mb-1 text-[11px] text-muted-foreground">平台预算</p>
                          <PersonalCredentialBudgetInline
                            credentialId={c.id}
                            userId={currentUser.id}
                            budgets={personalBudgets}
                            myModels={myModels}
                          />
                        </div>
                      ) : null}
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          )
        })}
      </>
    ),
    [
      hasAuthSession,
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
    ]
  )

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-12">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className={outerClass}>
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-base">提供商凭据</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">{credentialsBody}</CardContent>
      </Card>

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

      <AlertDialog
        open={credentialPendingDelete !== null}
        onOpenChange={(nextOpen) => {
          if (!nextOpen) {
            setCredentialPendingDelete(null)
          }
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除凭据</AlertDialogTitle>
            <AlertDialogDescription>
              {credentialPendingDelete
                ? `确定删除「${credentialPendingDelete.name}」？将同时删除所有引用该凭据的个人注册模型，并更新虚拟 Key / 路由中的模型白名单。`
                : ''}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleteMutation.isPending}>取消</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              disabled={deleteMutation.isPending || credentialPendingDelete === null}
              onClick={() => {
                if (credentialPendingDelete) {
                  deleteMutation.mutate(credentialPendingDelete.id)
                }
              }}
            >
              {deleteMutation.isPending ? '删除中…' : '删除'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

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
          修改账号名称、启用状态或轮换 {form.apiKeyLabel}；当前密钥可按需查看完整明文。
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
