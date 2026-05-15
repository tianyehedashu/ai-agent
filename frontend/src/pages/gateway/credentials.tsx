/**
 * AI Gateway · 凭据管理
 */

import { useEffect, useState } from 'react'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2 } from 'lucide-react'
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
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useToast } from '@/hooks/use-toast'

const PROVIDERS = [
  'openai',
  'anthropic',
  'azure',
  'dashscope',
  'deepseek',
  'volcengine',
  'zhipuai',
  'gemini',
  'cohere',
  'mistral',
  'fireworks',
  'together_ai',
] as const

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
  const [open, setOpen] = useState(false)
  const [credentialPendingDelete, setCredentialPendingDelete] = useState<ProviderCredential | null>(
    null
  )

  const { data: items, isLoading } = useQuery({
    queryKey: ['gateway', 'credentials'],
    queryFn: () => gatewayApi.listCredentials(),
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
      toast({ title: `已导入 ${String(r.created)} 条凭据` })
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

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold">凭据管理</h2>
          <p className="text-sm text-muted-foreground">
            归属当前团队上下文，由 Gateway Router 拉取调用；注册模型前请先在此配置并启用凭据
          </p>
        </div>
        <div className="flex gap-2">
          {canWrite && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                importMutation.mutate()
              }}
            >
              从「我的模型」导入
            </Button>
          )}
          {canWrite && (
            <Button
              size="sm"
              onClick={() => {
                setOpen(true)
              }}
            >
              <Plus className="mr-1.5 h-4 w-4" />
              新增凭据
            </Button>
          )}
        </div>
      </div>

      <Card>
        <CardContent className="p-0">
          <table className="w-full text-sm">
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
                    加载中...
                  </td>
                </tr>
              )}
              {!isLoading && (items?.length ?? 0) === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-6 text-center text-muted-foreground">
                    暂无凭据
                  </td>
                </tr>
              )}
              {items?.map((c: ProviderCredential) => {
                const editable = canEditGatewayCredential(c, canWrite, isPlatformAdmin)
                return (
                  <tr key={c.id} className="border-b last:border-0 hover:bg-muted/20">
                    <td className="px-4 py-2">
                      {canWrite ? (
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
                          <Button variant="ghost" size="sm" className="h-7 px-2 text-xs" asChild>
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
        </CardContent>
      </Card>

      <CreateCredentialDialog
        open={open}
        onOpenChange={setOpen}
        isPlatformAdmin={isPlatformAdmin}
        onSubmit={(v) => {
          createMutation.mutate({
            provider: v.provider,
            name: v.name,
            api_key: v.api_key,
            api_base: v.api_base?.trim() ? v.api_base : undefined,
            scope: v.scope,
          })
        }}
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

interface CreateValues {
  provider: string
  name: string
  api_key: string
  api_base?: string
  /** 仅平台管理员创建时可传 system */
  scope: 'team' | 'system'
}

function CreateCredentialDialog({
  open,
  onOpenChange,
  isPlatformAdmin,
  onSubmit,
}: Readonly<{
  open: boolean
  onOpenChange: (v: boolean) => void
  isPlatformAdmin: boolean
  onSubmit: (v: CreateValues) => void
}>): React.JSX.Element {
  const [values, setValues] = useState<CreateValues>({
    provider: 'openai',
    name: '',
    api_key: '',
    api_base: '',
    scope: 'team',
  })

  useEffect(() => {
    if (open) {
      setValues({
        provider: 'openai',
        name: '',
        api_key: '',
        api_base: '',
        scope: 'team',
      })
    }
  }, [open])

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>新增凭据</DialogTitle>
        </DialogHeader>
        <div className="space-y-3 py-2">
          {isPlatformAdmin ? (
            <div>
              <Label>作用域</Label>
              <Select
                value={values.scope}
                onValueChange={(v) => {
                  setValues({ ...values, scope: v as 'team' | 'system' })
                }}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="team">团队（当前工作区）</SelectItem>
                  <SelectItem value="system">系统全局</SelectItem>
                </SelectContent>
              </Select>
            </div>
          ) : null}
          <div>
            <Label>名称</Label>
            <Input
              value={values.name}
              onChange={(e) => {
                setValues({ ...values, name: e.target.value })
              }}
              placeholder="OpenAI 主账号 / Azure 测试线 ..."
            />
          </div>
          <div>
            <Label>提供商</Label>
            <Select
              value={values.provider}
              onValueChange={(v) => {
                setValues({ ...values, provider: v })
              }}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {PROVIDERS.map((p) => (
                  <SelectItem key={p} value={p}>
                    {p}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label>API Key</Label>
            <Input
              type="password"
              value={values.api_key}
              onChange={(e) => {
                setValues({ ...values, api_key: e.target.value })
              }}
            />
          </div>
          <div>
            <Label>api_base（可选）</Label>
            <Input
              value={values.api_base ?? ''}
              onChange={(e) => {
                setValues({ ...values, api_base: e.target.value })
              }}
              placeholder="https://api.openai.com/v1"
            />
          </div>
        </div>
        <DialogFooter>
          <Button
            variant="ghost"
            onClick={() => {
              onOpenChange(false)
            }}
          >
            取消
          </Button>
          <Button
            onClick={() => {
              if (!values.name || !values.api_key) return
              const payload: CreateValues = { ...values }
              if (!isPlatformAdmin) {
                payload.scope = 'team'
              }
              onSubmit(payload)
            }}
            disabled={!values.name || !values.api_key}
          >
            创建
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
