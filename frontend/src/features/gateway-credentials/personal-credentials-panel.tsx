/**
 * 个人凭据（/my-credentials）列表与编辑，用于 AI Gateway 凭据页「个人」Tab。
 *
 * 新增动作由外层 [`pages/gateway/credentials.tsx`](../../pages/gateway/credentials.tsx)
 * 的 `CreateCredentialDialog` 统一承担，本组件仅承载列表渲染与编辑弹窗。
 */

import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from 'react'
import type React from 'react'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { gatewayApi, type ProviderCredential } from '@/api/gateway'
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
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { useToast } from '@/hooks/use-toast'
import { Eye, EyeOff, Key, Loader2, Pencil, Plus, Trash2 } from '@/lib/lucide-icons'
import { useAuthStore } from '@/stores/auth'

import { USER_GATEWAY_CREDENTIAL_PROVIDER_IDS, credentialProviderLabel } from './constants'
import { ExtraFieldsRenderer } from './credential-extra-fields'
import {
  compactExtra,
  extraToFormValues,
  type CredentialExtraValues,
} from './credential-extra-utils'
import { invalidateCredentialProbeCache } from './credential-probe-cache'
import { displayListApiKeyMasked } from './mask-display'
import { apiKeyLabelForProvider, extraFieldsForProvider } from './provider-schemas'
import { invalidateCredentialSummariesCache } from './use-credential-directory'

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
  const [showFullMaskedInList, setShowFullMaskedInList] = useState(false)
  const [showKey, setShowKey] = useState(false)
  const [editCred, setEditCred] = useState<ProviderCredential | null>(null)
  const [addModelsCred, setAddModelsCred] = useState<ProviderCredential | null>(null)
  const [credentialPendingDelete, setCredentialPendingDelete] = useState<ProviderCredential | null>(
    null
  )
  const [formName, setFormName] = useState('')
  const [formApiKey, setFormApiKey] = useState('')
  const [formApiBase, setFormApiBase] = useState('')
  const [formExtra, setFormExtra] = useState<CredentialExtraValues>({})
  const [formIsActive, setFormIsActive] = useState(true)

  const { data: credentials = [], isLoading } = useQuery({
    queryKey: ['gateway', 'my-credentials'],
    queryFn: () => gatewayApi.listMyCredentials(),
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

  const resetEditForm = useCallback((): void => {
    setFormName('')
    setFormApiKey('')
    setFormApiBase('')
    setFormExtra({})
    setFormIsActive(true)
    setShowKey(false)
  }, [])

  const openEdit = useCallback((c: ProviderCredential): void => {
    setEditCred(c)
    setFormName(c.name)
    setFormApiKey('')
    setFormApiBase(c.api_base ?? '')
    setFormExtra(extraToFormValues(c.extra))
    setFormIsActive(c.is_active)
    setShowKey(false)
  }, [])

  const editProvider = editCred?.provider ?? ''
  const editExtraFields = useMemo(() => extraFieldsForProvider(editProvider), [editProvider])
  const editApiKeyLabel = apiKeyLabelForProvider(editProvider)

  const updateMutation = useMutation({
    mutationFn: () => {
      if (!editCred) throw new Error('no credential')
      const compactedExtra = compactExtra(formExtra)
      return gatewayApi.updateMyCredential(editCred.id, {
        name: formName.trim() || editCred.name,
        ...(formApiKey.trim() ? { api_key: formApiKey.trim() } : {}),
        api_base: formApiBase.trim() || null,
        extra: Object.keys(compactedExtra).length > 0 ? compactedExtra : undefined,
        is_active: formIsActive,
      })
    },
    onSuccess: () => {
      if (editCred) {
        invalidateCredentialProbeCache(queryClient, 'user', editCred.id)
      }
      invalidate()
      setEditCred(null)
      resetEditForm()
      toast({ title: '已保存' })
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '保存失败', description: e.message })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: gatewayApi.deleteMyCredential,
    onSuccess: (_data, credentialId) => {
      invalidateCredentialProbeCache(queryClient, 'user', credentialId)
      invalidate()
      setCredentialPendingDelete(null)
      if (editCred?.id === credentialId) {
        setEditCred(null)
        resetEditForm()
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

  const submitEdit = (): void => {
    if (!editCred) return
    const nameUnchanged = formName.trim() === editCred.name
    const baseUnchanged = formApiBase.trim() === (editCred.api_base ?? '').trim()
    const keyEmpty = !formApiKey.trim()
    const activeUnchanged = formIsActive === editCred.is_active
    const extraChanged =
      JSON.stringify(compactExtra(formExtra)) !==
      JSON.stringify(compactExtra(extraToFormValues(editCred.extra)))
    if (keyEmpty && nameUnchanged && baseUnchanged && activeUnchanged && !extraChanged) {
      toast({
        variant: 'destructive',
        title: '请至少修改名称、Base、扩展字段、启用状态或填写新 API Key',
      })
      return
    }
    updateMutation.mutate()
  }

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
                    <li
                      key={c.id}
                      className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 text-sm"
                    >
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
          if (!o) {
            setEditCred(null)
            resetEditForm()
          }
        }}
      >
        <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>编辑凭据</DialogTitle>
          </DialogHeader>
          <div className="grid gap-3 py-2">
            <div className="flex items-center justify-between rounded-md border px-3 py-2">
              <Label htmlFor="my-cred-active" className="cursor-pointer font-normal">
                启用该账号
              </Label>
              <Switch
                id="my-cred-active"
                checked={formIsActive}
                onCheckedChange={setFormIsActive}
              />
            </div>
            <div className="space-y-2">
              <Label>账号名称</Label>
              <Input
                value={formName}
                onChange={(e) => {
                  setFormName(e.target.value)
                }}
              />
            </div>
            <div className="space-y-2">
              <Label>新 {editApiKeyLabel}（留空则不变）</Label>
              <div className="relative">
                <Input
                  type={showKey ? 'text' : 'password'}
                  value={formApiKey}
                  onChange={(e) => {
                    setFormApiKey(e.target.value)
                  }}
                  className="pr-10"
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="absolute right-1 top-1/2 h-8 w-8 -translate-y-1/2"
                  onClick={() => {
                    setShowKey((v) => !v)
                  }}
                >
                  {showKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </Button>
              </div>
            </div>
            <div className="space-y-2">
              <Label>API Base</Label>
              <Input
                type="url"
                value={formApiBase}
                onChange={(e) => {
                  setFormApiBase(e.target.value)
                }}
              />
            </div>
            <ExtraFieldsRenderer
              fields={editExtraFields}
              values={formExtra}
              onChange={setFormExtra}
              idPrefix="edit-cred-extra"
            />
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setEditCred(null)
              }}
            >
              取消
            </Button>
            <Button onClick={submitEdit} disabled={updateMutation.isPending}>
              {updateMutation.isPending ? '保存中…' : '保存'}
            </Button>
          </DialogFooter>
        </DialogContent>
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
