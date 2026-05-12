/**
 * AI Gateway · 凭据管理
 */

import { useState } from 'react'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2 } from 'lucide-react'

import { gatewayApi, type ProviderCredential } from '@/api/gateway'
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

export default function GatewayCredentialsPage(): React.JSX.Element {
  const { canWrite } = useGatewayPermission()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [open, setOpen] = useState(false)

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

  const deleteMutation = useMutation({
    mutationFn: (id: string) => gatewayApi.deleteCredential(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'credentials'] })
      toast({ title: '已删除' })
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

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold">凭据管理</h2>
          <p className="text-sm text-muted-foreground">
            归属当前团队上下文，由 Gateway Router 拉取调用
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
                <th className="px-4 py-2 text-left font-medium">提供商</th>
                <th className="px-4 py-2 text-left font-medium">作用域</th>
                <th className="px-4 py-2 text-left font-medium">api_base</th>
                <th className="px-4 py-2 text-left font-medium">状态</th>
                <th className="px-4 py-2 text-left font-medium" />
              </tr>
            </thead>
            <tbody>
              {isLoading && (
                <tr>
                  <td colSpan={6} className="px-4 py-6 text-center text-muted-foreground">
                    加载中...
                  </td>
                </tr>
              )}
              {!isLoading && (items?.length ?? 0) === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-6 text-center text-muted-foreground">
                    暂无凭据
                  </td>
                </tr>
              )}
              {items?.map((c: ProviderCredential) => (
                <tr key={c.id} className="border-b last:border-0 hover:bg-muted/20">
                  <td className="px-4 py-2">{c.name}</td>
                  <td className="px-4 py-2 font-mono text-xs">{c.provider}</td>
                  <td className="px-4 py-2 text-xs">{c.scope}</td>
                  <td className="px-4 py-2 text-xs">{c.api_base ?? '—'}</td>
                  <td className="px-4 py-2 text-xs">{c.is_active ? '启用' : '禁用'}</td>
                  <td className="px-4 py-2">
                    {canWrite && (
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-7 w-7"
                        onClick={() => {
                          if (confirm(`删除 ${c.name}?`)) deleteMutation.mutate(c.id)
                        }}
                      >
                        <Trash2 className="h-3.5 w-3.5 text-destructive" />
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>

      <CreateCredentialDialog
        open={open}
        onOpenChange={setOpen}
        onSubmit={(v) => {
          createMutation.mutate(v)
        }}
      />
    </div>
  )
}

interface CreateValues {
  provider: string
  name: string
  api_key: string
  api_base?: string
}

function CreateCredentialDialog({
  open,
  onOpenChange,
  onSubmit,
}: Readonly<{
  open: boolean
  onOpenChange: (v: boolean) => void
  onSubmit: (v: CreateValues) => void
}>): React.JSX.Element {
  const [values, setValues] = useState<CreateValues>({
    provider: 'openai',
    name: '',
    api_key: '',
    api_base: '',
  })
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>新增凭据</DialogTitle>
        </DialogHeader>
        <div className="space-y-3 py-2">
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
              onSubmit(values)
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
