/**
 * AI Gateway · 凭据（个人 / 团队）
 */

import { lazy, Suspense, startTransition, useCallback, useMemo, useState } from 'react'
import type React from 'react'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

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
import { Card, CardContent } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsContent, TabsList } from '@/components/ui/tabs'
import { isConfigManagedSystemCredential } from '@/features/gateway-credentials/config-managed-credential'
import {
  CreateCredentialDialog,
  type CreateCredentialValues,
} from '@/features/gateway-credentials/create-credential-dialog'
import { PersonalCredentialsPanel } from '@/features/gateway-credentials/personal-credentials-panel'
import {
  defaultApiBaseForProvider,
  providerLabel,
  type CredentialFormScope,
} from '@/features/gateway-credentials/provider-schemas'
import type { CredentialUpstreamScope } from '@/features/gateway-credentials/types'
import { GatewayScopeTabTriggers } from '@/features/gateway-models/gateway-scope-tabs'
import {
  credentialDetailAddModelsHref,
  credentialDetailHref,
} from '@/features/gateway-models/paths'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useGatewayScopeTab } from '@/hooks/use-gateway-scope-tab'
import { useToast } from '@/hooks/use-toast'
import { Loader2, Plus, Trash2 } from '@/lib/lucide-icons'

const AddModelsDialog = lazy(() =>
  import('@/features/gateway-credentials/add-models-dialog').then((m) => ({
    default: m.AddModelsDialog,
  }))
)

interface JustCreatedCredential {
  id: string
  provider: string
  name: string
  scope: CredentialUpstreamScope
  is_active: boolean
}

function canEditGatewayCredential(
  c: ProviderCredential,
  canWrite: boolean,
  isPlatformAdmin: boolean
): boolean {
  return (c.scope === 'team' && canWrite) || (c.scope === 'system' && isPlatformAdmin)
}

function CredentialApiBaseCell({
  credential,
}: Readonly<{ credential: ProviderCredential }>): React.JSX.Element {
  const base = credential.api_base ?? ''
  if (!base) return <span className="text-muted-foreground">—</span>
  const defaultBase = defaultApiBaseForProvider(credential.provider)
  const isDefault = Boolean(defaultBase) && base === defaultBase
  const keys = credential.extra ? Object.keys(credential.extra) : []
  return (
    <div className="flex flex-col gap-0.5">
      <div className="flex flex-wrap items-center gap-1">
        <span className="break-all">{base}</span>
        {isDefault ? (
          <Badge variant="outline" className="px-1 py-0 text-[10px]">
            默认
          </Badge>
        ) : null}
      </div>
      {keys.length > 0 ? (
        <span className="font-mono text-[10px] text-muted-foreground">
          extra: {keys.join(', ')}
        </span>
      ) : null}
    </div>
  )
}

export default function GatewayCredentialsPage(): React.JSX.Element {
  const { canWrite, isPlatformAdmin } = useGatewayPermission()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [open, setOpen] = useState(false)
  const [pendingProvider, setPendingProvider] = useState<string | undefined>(undefined)
  const [credentialPendingDelete, setCredentialPendingDelete] = useState<ProviderCredential | null>(
    null
  )
  const [justCreated, setJustCreated] = useState<JustCreatedCredential | null>(null)

  const closeCreateUi = useCallback((): void => {
    setOpen(false)
    setPendingProvider(undefined)
  }, [])

  const { scopeTab: activeTab, setScopeTab: setActiveTab } = useGatewayScopeTab({
    onBeforeTabChange: closeCreateUi,
  })

  const { data: items, isLoading } = useQuery({
    queryKey: ['gateway', 'credentials'],
    queryFn: () => gatewayApi.listCredentials(),
    enabled: activeTab === 'shared',
  })

  const closeCreateDialog = useCallback((): void => {
    setOpen(false)
    setPendingProvider(undefined)
  }, [])

  const openAddModelsAfterCreate = useCallback(
    (cred: ProviderCredential, scope: CredentialUpstreamScope): void => {
      closeCreateDialog()
      setJustCreated({
        id: cred.id,
        provider: cred.provider,
        name: cred.name,
        scope,
        is_active: cred.is_active,
      })
      toast({
        title: '凭据已创建',
        description: '正在准备添加模型，也可稍后在凭据详情中操作。',
      })
    },
    [closeCreateDialog, toast]
  )

  const createManagedMutation = useMutation({
    mutationFn: gatewayApi.createCredential,
    onSuccess: (cred) => {
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'credentials'] })
      openAddModelsAfterCreate(cred, 'team')
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '创建失败', description: e.message })
    },
  })

  const createUserMutation = useMutation({
    mutationFn: gatewayApi.createMyCredential,
    onSuccess: (cred) => {
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'my-credentials'] })
      void queryClient.invalidateQueries({ queryKey: ['provider-configs'] })
      openAddModelsAfterCreate(cred, 'user')
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '创建失败', description: e.message })
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: GatewayCredentialUpdateBody }) =>
      gatewayApi.updateCredential(id, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'credentials'] })
      toast({ title: '凭据已更新' })
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '更新失败', description: e.message })
    },
  })

  const importMutation = useMutation({
    mutationFn: gatewayApi.importFromUserConfig,
    onSuccess: (r) => {
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'credentials'] })
      toast({ title: `已导入 ${String(r.created)} 条` })
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '导入失败', description: e.message })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: gatewayApi.deleteCredential,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'credentials'] })
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'models'] })
      setCredentialPendingDelete(null)
      toast({ title: '凭据已删除', description: '关联的注册模型已一并移除' })
    },
    onError: (e: Error) => {
      setCredentialPendingDelete(null)
      toast({ variant: 'destructive', title: '删除失败', description: e.message })
    },
  })

  const onCreateSubmit = (v: CreateCredentialValues): void => {
    if (v.scope === 'user') {
      createUserMutation.mutate({
        provider: v.provider,
        name: v.name,
        api_key: v.api_key,
        api_base: v.api_base ?? null,
        extra: v.extra,
      })
      return
    }
    createManagedMutation.mutate({
      provider: v.provider,
      name: v.name,
      api_key: v.api_key,
      api_base: v.api_base,
      extra: v.extra,
      scope: v.scope,
    })
  }

  const allowedScopes = useMemo<ReadonlyArray<CredentialFormScope>>(() => {
    const scopes: CredentialFormScope[] = ['user']
    if (canWrite) scopes.push('team')
    if (isPlatformAdmin) scopes.push('system')
    return scopes
  }, [canWrite, isPlatformAdmin])
  // 注意：此处 'team' 是 `CredentialScope.team`（凭据写入归属），
  // 与 ScopeTab 的 'shared' / 'personal' 是不同概念，禁止合并字面量。
  const defaultScope: CredentialFormScope = activeTab === 'personal' ? 'user' : 'team'
  const createSubmitting = createManagedMutation.isPending || createUserMutation.isPending

  const handleOpenCreate = useCallback((provider?: string): void => {
    setPendingProvider(provider)
    setOpen(true)
  }, [])

  const handleDialogOpenChange = useCallback((next: boolean): void => {
    setOpen(next)
    if (!next) setPendingProvider(undefined)
  }, [])

  return (
    <div className="space-y-4">
      <Tabs
        value={activeTab}
        onValueChange={(v) => {
          if (v === 'personal' || v === 'shared') {
            startTransition(() => {
              setActiveTab(v)
            })
          }
        }}
      >
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <TabsList>
            <GatewayScopeTabTriggers />
          </TabsList>
          <div className="flex flex-wrap gap-2">
            {activeTab === 'shared' && canWrite ? (
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  importMutation.mutate()
                }}
                disabled={importMutation.isPending}
              >
                导入
              </Button>
            ) : null}
            <Button
              size="sm"
              onClick={() => {
                handleOpenCreate()
              }}
            >
              <Plus className="mr-1.5 h-4 w-4" />
              新增
            </Button>
          </div>
        </div>

        <TabsContent value="personal" className="mt-4 focus-visible:outline-none">
          <PersonalCredentialsPanel onAddCredential={handleOpenCreate} />
        </TabsContent>

        <TabsContent value="shared" className="mt-4 focus-visible:outline-none">
          <Card>
            <CardContent className="p-0">
              <ScrollArea className="w-full overscroll-y-contain">
                <table className="w-full min-w-[720px] text-sm">
                  <thead className="border-b bg-muted/30 text-xs uppercase text-muted-foreground">
                    <tr>
                      <th className="px-4 py-2 text-left font-medium">名称</th>
                      <th className="px-4 py-2 text-left font-medium">API Key</th>
                      <th className="px-4 py-2 text-left font-medium">提供商</th>
                      <th className="px-4 py-2 text-left font-medium">作用域</th>
                      <th className="px-4 py-2 text-left font-medium">api_base</th>
                      <th className="px-4 py-2 text-left font-medium">启用</th>
                      <th className="px-4 py-2 text-left font-medium">操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {isLoading && (
                      <tr>
                        <td colSpan={7} className="px-4 py-6 text-center text-muted-foreground">
                          加载中…
                        </td>
                      </tr>
                    )}
                    {!isLoading && (items?.length ?? 0) === 0 && (
                      <tr>
                        <td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">
                          <span className="mr-3">暂无凭据</span>
                          {canWrite ? (
                            <Button
                              size="sm"
                              variant="secondary"
                              onClick={() => {
                                handleOpenCreate()
                              }}
                            >
                              新增
                            </Button>
                          ) : null}
                        </td>
                      </tr>
                    )}
                    {items?.map((c: ProviderCredential) => {
                      const editable = canEditGatewayCredential(c, canWrite, isPlatformAdmin)
                      const configManaged = isConfigManagedSystemCredential(c)
                      return (
                        <tr key={c.id} className="border-b last:border-0 hover:bg-muted/20">
                          <td className="px-4 py-2">
                            <div className="flex flex-wrap items-center gap-2">
                              {editable ? (
                                <Link
                                  to={credentialDetailHref(c.id)}
                                  className="font-medium text-primary underline-offset-4 hover:underline"
                                >
                                  {c.name}
                                </Link>
                              ) : (
                                <span className="font-medium">{c.name}</span>
                              )}
                              {configManaged ? (
                                <Badge variant="secondary" className="text-[10px] font-normal">
                                  配置同步
                                </Badge>
                              ) : null}
                            </div>
                          </td>
                          <td className="px-4 py-2 font-mono text-xs text-muted-foreground">
                            {c.api_key_masked}
                          </td>
                          <td className="px-4 py-2 text-xs">
                            <div className="flex flex-col">
                              <span className="font-medium">{providerLabel(c.provider)}</span>
                              <span
                                className="font-mono text-[10px] text-muted-foreground"
                                title={c.provider}
                              >
                                {c.provider}
                              </span>
                            </div>
                          </td>
                          <td className="px-4 py-2 text-xs">{c.scope}</td>
                          <td className="px-4 py-2 text-xs">
                            <CredentialApiBaseCell credential={c} />
                          </td>
                          <td className="px-4 py-2">
                            {editable ? (
                              <Switch
                                checked={c.is_active}
                                disabled={updateMutation.isPending}
                                onCheckedChange={(checked) => {
                                  updateMutation.mutate({ id: c.id, body: { is_active: checked } })
                                }}
                                aria-label={c.is_active ? '停用凭据' : '启用凭据'}
                              />
                            ) : (
                              <span className="text-xs text-muted-foreground">
                                {c.is_active ? '启用' : '禁用'}
                              </span>
                            )}
                          </td>
                          <td className="px-4 py-2">
                            {editable ? (
                              <div className="flex items-center gap-0.5">
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className="h-7 px-2 text-xs"
                                  asChild
                                >
                                  <Link to={credentialDetailHref(c.id)}>详情</Link>
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className="h-7 px-2 text-xs"
                                  asChild
                                >
                                  <Link to={credentialDetailAddModelsHref(c.id)}>添加模型</Link>
                                </Button>
                                <Button
                                  size="icon"
                                  variant="ghost"
                                  className="h-7 w-7 text-destructive hover:text-destructive"
                                  disabled={deleteMutation.isPending}
                                  onClick={() => {
                                    setCredentialPendingDelete(c)
                                  }}
                                  aria-label="删除凭据"
                                >
                                  <Trash2 className="h-3.5 w-3.5" />
                                </Button>
                              </div>
                            ) : null}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </ScrollArea>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <CreateCredentialDialog
        open={open}
        onOpenChange={handleDialogOpenChange}
        allowedScopes={allowedScopes}
        defaultScope={defaultScope}
        defaultProvider={pendingProvider}
        submitting={createSubmitting}
        onSubmit={onCreateSubmit}
      />

      {justCreated ? (
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
            onOpenChange={(next: boolean) => {
              if (!next) setJustCreated(null)
            }}
            scope={justCreated.scope}
            credentialId={justCreated.id}
            provider={justCreated.provider}
            credentialName={justCreated.name}
            isActive={justCreated.is_active}
            onboardingHint="凭据已创建。现在可以快速添加模型，也可以稍后再来。"
          />
        </Suspense>
      ) : null}

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
                ? isConfigManagedSystemCredential(credentialPendingDelete)
                  ? `确定删除「${credentialPendingDelete.name}」？将同时删除所有引用该凭据的注册模型；此为配置同步凭据，下次从配置重载或重启后可能自动恢复。`
                  : `确定删除「${credentialPendingDelete.name}」？将同时删除所有引用该凭据的注册模型，并更新虚拟 Key / 路由中的模型白名单。`
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
    </div>
  )
}
