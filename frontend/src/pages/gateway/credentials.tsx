/**
 * AI Gateway · 凭据（个人 / 团队）
 */

import { useCallback, useEffect, useState } from 'react'
import type React from 'react'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2 } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'

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
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  CreateTeamManagedCredentialDialog,
  type TeamManagedCredentialCreateValues,
} from '@/features/gateway-credentials/create-team-managed-credential-dialog'
import { PersonalCredentialsPanel } from '@/features/gateway-credentials/personal-credentials-panel'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useToast } from '@/hooks/use-toast'

type CredentialTab = 'personal' | 'team'

function parseTab(raw: string | null): CredentialTab {
  return raw === 'personal' || raw === 'team' ? raw : 'team'
}

function canEditGatewayCredential(
  c: ProviderCredential,
  canWrite: boolean,
  isPlatformAdmin: boolean
): boolean {
  return (c.scope === 'team' && canWrite) || (c.scope === 'system' && isPlatformAdmin)
}

export default function GatewayCredentialsPage(): React.JSX.Element {
  const { canWrite, isPlatformAdmin } = useGatewayPermission()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [searchParams, setSearchParams] = useSearchParams()
  const [open, setOpen] = useState(false)
  const [credentialPendingDelete, setCredentialPendingDelete] = useState<ProviderCredential | null>(
    null
  )

  const activeTab = parseTab(searchParams.get('tab'))

  const setActiveTab = useCallback(
    (next: CredentialTab): void => {
      setOpen(false)
      setSearchParams(
        (prev) => {
          const n = new URLSearchParams(prev)
          n.set('tab', next)
          return n
        },
        { replace: true }
      )
    },
    [setSearchParams]
  )

  useEffect(() => {
    const raw = searchParams.get('tab')
    if (raw !== null && raw !== 'personal' && raw !== 'team') {
      setOpen(false)
      setSearchParams(
        (prev) => {
          const n = new URLSearchParams(prev)
          n.set('tab', 'team')
          return n
        },
        { replace: true }
      )
    }
  }, [searchParams, setSearchParams])

  const { data: items, isLoading } = useQuery({
    queryKey: ['gateway', 'credentials'],
    queryFn: () => gatewayApi.listCredentials(),
    enabled: activeTab === 'team',
  })

  const createMutation = useMutation({
    mutationFn: gatewayApi.createCredential,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'credentials'] })
      setOpen(false)
      toast({ title: '凭据已创建' })
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
      setCredentialPendingDelete(null)
      toast({ title: '凭据已删除' })
    },
    onError: (e: Error) => {
      setCredentialPendingDelete(null)
      toast({ variant: 'destructive', title: '删除失败', description: e.message })
    },
  })

  const onCreateSubmit = (v: TeamManagedCredentialCreateValues): void => {
    createMutation.mutate({
      provider: v.provider,
      name: v.name,
      api_key: v.api_key,
      api_base: v.api_base?.trim() ? v.api_base : undefined,
      scope: v.scope,
    })
  }

  return (
    <div className="space-y-4">
      <Tabs
        value={activeTab}
        onValueChange={(v) => {
          setActiveTab(parseTab(v))
        }}
      >
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <TabsList>
            <TabsTrigger value="personal">个人</TabsTrigger>
            <TabsTrigger value="team">团队</TabsTrigger>
          </TabsList>
          {activeTab === 'team' && canWrite ? (
            <div className="flex flex-wrap gap-2">
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
              <Button
                size="sm"
                onClick={() => {
                  setOpen(true)
                }}
              >
                <Plus className="mr-1.5 h-4 w-4" />
                新增
              </Button>
            </div>
          ) : null}
        </div>

        <TabsContent value="personal" className="mt-4 focus-visible:outline-none">
          <PersonalCredentialsPanel />
        </TabsContent>

        <TabsContent value="team" className="mt-4 focus-visible:outline-none">
          <Card>
            <CardContent className="p-0">
              <ScrollArea className="w-full">
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
                                setOpen(true)
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
                      return (
                        <tr key={c.id} className="border-b last:border-0 hover:bg-muted/20">
                          <td className="px-4 py-2">
                            {editable ? (
                              <Link
                                to={`/gateway/credentials/${c.id}`}
                                className="font-medium text-primary underline-offset-4 hover:underline"
                              >
                                {c.name}
                              </Link>
                            ) : (
                              <span className="font-medium">{c.name}</span>
                            )}
                          </td>
                          <td className="px-4 py-2 font-mono text-xs text-muted-foreground">
                            {c.api_key_masked}
                          </td>
                          <td className="px-4 py-2 font-mono text-xs">{c.provider}</td>
                          <td className="px-4 py-2 text-xs">{c.scope}</td>
                          <td className="px-4 py-2 text-xs">{c.api_base ?? '—'}</td>
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
                                  <Link to={`/gateway/credentials/${c.id}`}>详情</Link>
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

      <CreateTeamManagedCredentialDialog
        open={open}
        onOpenChange={setOpen}
        isPlatformAdmin={isPlatformAdmin}
        onSubmit={onCreateSubmit}
      />

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
                ? `确定删除「${credentialPendingDelete.name}」？若仍被网关模型引用，删除将失败并提示冲突。`
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
