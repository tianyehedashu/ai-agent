/**
 * AI Gateway · 凭据详情（编辑、轮换密钥、删除、关联模型）
 */

import { useEffect, useMemo, useState } from 'react'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronRight, Trash2 } from 'lucide-react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import {
  gatewayApi,
  type GatewayCredentialUpdateBody,
  type GatewayModel,
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
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useToast } from '@/hooks/use-toast'

function canEditGatewayCredential(
  c: ProviderCredential,
  canWrite: boolean,
  isPlatformAdmin: boolean
): boolean {
  return (c.scope === 'team' && canWrite) || (c.scope === 'system' && isPlatformAdmin)
}

export default function GatewayCredentialDetailPage(): React.JSX.Element {
  const { credentialId } = useParams<{ credentialId: string }>()
  const id = credentialId ?? ''
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const { canWrite, isPlatformAdmin } = useGatewayPermission()
  const [deleteOpen, setDeleteOpen] = useState(false)

  const [name, setName] = useState('')
  const [apiBase, setApiBase] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [isActive, setIsActive] = useState(true)

  const {
    data: cred,
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: ['gateway', 'credential', id],
    queryFn: () => gatewayApi.getCredential(id),
    enabled: id.length > 0,
  })

  const editable = cred ? canEditGatewayCredential(cred, canWrite, isPlatformAdmin) : false

  useEffect(() => {
    if (!cred) return
    setName(cred.name)
    setApiBase(cred.api_base ?? '')
    setApiKey('')
    setIsActive(cred.is_active)
  }, [cred])

  const synced = useMemo(() => {
    if (!cred) return true
    return (
      name === cred.name &&
      (apiBase.trim() || '') === (cred.api_base ?? '') &&
      isActive === cred.is_active &&
      apiKey === ''
    )
  }, [cred, name, apiBase, isActive, apiKey])

  const { data: linkedModels, isLoading: modelsLoading } = useQuery({
    queryKey: ['gateway', 'models', 'by-credential', id],
    queryFn: () => gatewayApi.listModels({ credential_id: id }),
    enabled: id.length > 0,
  })

  const updateMutation = useMutation({
    mutationFn: ({ cid, body }: { cid: string; body: GatewayCredentialUpdateBody }) =>
      gatewayApi.updateCredential(cid, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'credential', id] })
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'credentials'] })
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'models'] })
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'models', 'by-credential', id] })
      setApiKey('')
      toast({ title: '凭据已更新' })
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '更新失败', description: e.message })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: gatewayApi.deleteCredential,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'credentials'] })
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'models'] })
      toast({ title: '凭据已删除' })
      navigate('/gateway/credentials?tab=team')
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '删除失败', description: e.message })
    },
  })

  if (!id) {
    return (
      <div className="text-sm text-muted-foreground">
        无效的凭据 ID。
        <Link
          to="/gateway/credentials?tab=team"
          className="ml-2 text-primary underline-offset-4 hover:underline"
        >
          返回列表
        </Link>
      </div>
    )
  }

  if (isLoading) {
    return <div className="text-sm text-muted-foreground">加载中…</div>
  }

  if (isError || !cred) {
    return (
      <div className="space-y-2 text-sm">
        <p className="text-destructive">
          {error instanceof Error ? error.message : '无法加载凭据'}
        </p>
        <Link
          to="/gateway/credentials?tab=team"
          className="text-primary underline-offset-4 hover:underline"
        >
          返回凭据列表
        </Link>
      </div>
    )
  }

  function handleSave(): void {
    if (!editable || !name.trim()) return
    const body: GatewayCredentialUpdateBody = {
      name: name.trim(),
      is_active: isActive,
      api_base: apiBase.trim() || null,
    }
    if (apiKey.trim()) {
      body.api_key = apiKey.trim()
    }
    updateMutation.mutate({ cid: id, body })
  }

  return (
    <div className="space-y-6">
      <nav className="flex flex-wrap items-center gap-1 text-sm text-muted-foreground">
        <Link to="/gateway/credentials?tab=team" className="hover:text-foreground">
          凭据管理
        </Link>
        <ChevronRight className="h-4 w-4 shrink-0" aria-hidden />
        <span className="font-medium text-foreground">{cred.name}</span>
      </nav>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-2xl font-semibold">{cred.name}</h2>
          <p className="text-sm text-muted-foreground">
            <span className="font-mono">{cred.provider}</span>
            <span className="mx-2">·</span>
            <span>{cred.scope}</span>
            {cred.scope === 'system' ? <span className="ml-2 text-xs">（系统全局）</span> : null}
          </p>
        </div>
        {editable ? (
          <div className="flex flex-wrap gap-2">
            <Button
              variant="destructive"
              size="sm"
              onClick={() => {
                setDeleteOpen(true)
              }}
            >
              <Trash2 className="mr-1.5 h-4 w-4" />
              删除
            </Button>
          </div>
        ) : null}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>凭据与密钥</CardTitle>
            <CardDescription>API Key 仅显示掩码；轮换请填写新密钥后保存。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label>API Key（掩码）</Label>
              <Input readOnly className="mt-1.5 font-mono text-xs" value={cred.api_key_masked} />
            </div>
            {editable ? (
              <>
                <div className="flex items-center justify-between gap-4 rounded-md border px-3 py-2">
                  <Label
                    htmlFor="cred-detail-active"
                    className="cursor-pointer text-sm font-normal"
                  >
                    启用
                  </Label>
                  <Switch
                    id="cred-detail-active"
                    checked={isActive}
                    onCheckedChange={setIsActive}
                  />
                </div>
                <div>
                  <Label htmlFor="cred-detail-name">名称</Label>
                  <Input
                    id="cred-detail-name"
                    className="mt-1.5"
                    value={name}
                    onChange={(e) => {
                      setName(e.target.value)
                    }}
                  />
                </div>
                <div>
                  <Label htmlFor="cred-detail-new-key">新 API Key（留空则不变）</Label>
                  <Input
                    id="cred-detail-new-key"
                    type="password"
                    autoComplete="new-password"
                    className="mt-1.5"
                    value={apiKey}
                    onChange={(e) => {
                      setApiKey(e.target.value)
                    }}
                  />
                </div>
                <div>
                  <Label htmlFor="cred-detail-base">api_base</Label>
                  <Input
                    id="cred-detail-base"
                    className="mt-1.5"
                    value={apiBase}
                    onChange={(e) => {
                      setApiBase(e.target.value)
                    }}
                    placeholder="https://..."
                  />
                </div>
                {cred.extra !== null && Object.keys(cred.extra).length > 0 ? (
                  <div>
                    <Label>extra（只读）</Label>
                    <pre className="mt-1.5 max-h-40 overflow-auto rounded-md border bg-muted/30 p-2 font-mono text-[11px] leading-relaxed">
                      {JSON.stringify(cred.extra, null, 2)}
                    </pre>
                  </div>
                ) : null}
                <Button
                  disabled={updateMutation.isPending || !name.trim() || synced}
                  onClick={() => {
                    handleSave()
                  }}
                >
                  {updateMutation.isPending ? '保存中…' : '保存更改'}
                </Button>
              </>
            ) : (
              <p className="text-sm text-muted-foreground">
                你无权编辑此凭据（系统凭据需平台管理员）。
              </p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>使用此凭据的注册模型</CardTitle>
            <CardDescription>
              在{' '}
              <Link
                to="/gateway/models"
                className="text-primary underline-offset-4 hover:underline"
              >
                模型与路由
              </Link>{' '}
              中可继续调整绑定。
            </CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            <table className="w-full text-sm">
              <thead className="border-b bg-muted/30 text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="px-4 py-2 text-left font-medium">名称</th>
                  <th className="px-4 py-2 text-left font-medium">调用面</th>
                  <th className="px-4 py-2 text-left font-medium">上游模型</th>
                  <th className="px-4 py-2 text-left font-medium">启用</th>
                </tr>
              </thead>
              <tbody>
                {modelsLoading ? (
                  <tr>
                    <td colSpan={4} className="px-4 py-6 text-center text-muted-foreground">
                      加载中…
                    </td>
                  </tr>
                ) : (linkedModels?.length ?? 0) === 0 ? (
                  <tr>
                    <td colSpan={4} className="px-4 py-6 text-center text-muted-foreground">
                      暂无注册模型使用此凭据
                    </td>
                  </tr>
                ) : (
                  (linkedModels ?? []).map((m: GatewayModel) => (
                    <tr key={m.id} className="border-b last:border-0 hover:bg-muted/20">
                      <td className="px-4 py-2">
                        <Link
                          to={`/gateway/models?credentialId=${encodeURIComponent(id)}&modelId=${encodeURIComponent(m.id)}`}
                          className="font-mono text-xs text-primary underline-offset-4 hover:underline"
                        >
                          {m.name}
                        </Link>
                      </td>
                      <td className="px-4 py-2 text-xs">{m.capability}</td>
                      <td className="px-4 py-2 font-mono text-xs">{m.real_model}</td>
                      <td className="px-4 py-2 text-xs">{m.enabled ? '是' : '否'}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </CardContent>
        </Card>
      </div>

      <AlertDialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除凭据</AlertDialogTitle>
            <AlertDialogDescription>
              确定删除「{cred.name}」？若仍被网关模型引用，删除将失败并提示冲突。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleteMutation.isPending}>取消</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              disabled={deleteMutation.isPending}
              onClick={() => {
                deleteMutation.mutate(id, {
                  onSettled: () => {
                    setDeleteOpen(false)
                  },
                })
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
