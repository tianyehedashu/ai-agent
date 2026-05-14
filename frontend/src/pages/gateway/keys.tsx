/**
 * AI Gateway · 虚拟 Key 管理
 */

import { useState } from 'react'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Copy, Plus, Trash2 } from 'lucide-react'
import { Link } from 'react-router-dom'

import { gatewayApi, type VirtualKey } from '@/api/gateway'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useToast } from '@/hooks/use-toast'

export default function GatewayKeysPage(): React.JSX.Element {
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const { canWrite } = useGatewayPermission()
  const [open, setOpen] = useState(false)
  const [createdKey, setCreatedKey] = useState<string | null>(null)

  const { data: keys, isLoading } = useQuery({
    queryKey: ['gateway', 'keys'],
    queryFn: () => gatewayApi.listKeys(),
  })

  const createMutation = useMutation({
    mutationFn: gatewayApi.createKey,
    onSuccess: (created) => {
      setCreatedKey(created.plain_key)
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'keys'] })
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '创建失败', description: e.message })
    },
  })

  const revokeMutation = useMutation({
    mutationFn: (id: string) => gatewayApi.revokeKey(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'keys'] })
      toast({ title: '已撤销' })
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '撤销失败', description: e.message })
    },
  })

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold">虚拟 Key</h2>
          <p className="text-sm text-muted-foreground">
            sk-gw- 前缀，仅用于 OpenAI 兼容入口 /v1/* 调用
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            若需使用平台 <span className="font-mono">sk-*</span> 并复用其他 API 能力，请到{' '}
            <Link
              to="/settings?tab=api"
              className="font-medium text-primary underline underline-offset-2"
            >
              设置 → API 密钥
            </Link>{' '}
            创建带 <span className="font-mono">gateway:proxy</span> 作用域的 Key。
          </p>
        </div>
        {canWrite && (
          <Button
            size="sm"
            onClick={() => {
              setOpen(true)
            }}
          >
            <Plus className="mr-1.5 h-4 w-4" />
            新建虚拟 Key
          </Button>
        )}
      </div>

      <Card>
        <CardContent className="p-0">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/30 text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-4 py-2 text-left font-medium">名称</th>
                <th className="px-4 py-2 text-left font-medium">Key</th>
                <th className="px-4 py-2 text-left font-medium">允许模型</th>
                <th className="px-4 py-2 text-left font-medium">每分钟请求 / 每分钟令牌</th>
                <th className="px-4 py-2 text-left font-medium">守卫</th>
                <th className="px-4 py-2 text-left font-medium">状态</th>
                <th className="px-4 py-2 text-left font-medium" />
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
              {!isLoading && (keys?.length ?? 0) === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-6 text-center text-muted-foreground">
                    暂无虚拟 Key
                  </td>
                </tr>
              )}
              {keys
                ?.filter((k) => !k.is_system)
                .map((k: VirtualKey) => (
                  <tr key={k.id} className="border-b last:border-0 hover:bg-muted/20">
                    <td className="px-4 py-2 font-medium">{k.name}</td>
                    <td className="px-4 py-2 font-mono text-xs">{k.masked_key}</td>
                    <td className="px-4 py-2 text-xs">
                      {k.allowed_models.length === 0 ? '全部' : k.allowed_models.join(', ')}
                    </td>
                    <td className="px-4 py-2 text-xs tabular-nums">
                      {`${String(k.rpm_limit ?? '∞')} / ${String(k.tpm_limit ?? '∞')}`}
                    </td>
                    <td className="px-4 py-2 text-xs">{k.guardrail_enabled ? '已启用' : '关闭'}</td>
                    <td className="px-4 py-2 text-xs">{k.is_active ? '可用' : '已撤销'}</td>
                    <td className="px-4 py-2">
                      {canWrite && k.is_active && (
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7"
                          onClick={() => {
                            if (confirm(`确认撤销 ${k.name}?`)) revokeMutation.mutate(k.id)
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

      <CreateKeyDialog
        open={open}
        onOpenChange={(v) => {
          setOpen(v)
          if (!v) setCreatedKey(null)
        }}
        onSubmit={(values) => {
          createMutation.mutate(values)
        }}
        plaintext={createdKey}
      />
    </div>
  )
}

interface CreateKeyValues {
  name: string
  guardrail_enabled: boolean
  store_full_messages: boolean
  rpm_limit?: number | null
  tpm_limit?: number | null
}

function CreateKeyDialog({
  open,
  onOpenChange,
  onSubmit,
  plaintext,
}: Readonly<{
  open: boolean
  onOpenChange: (v: boolean) => void
  onSubmit: (v: CreateKeyValues) => void
  plaintext: string | null
}>): React.JSX.Element {
  const [values, setValues] = useState<CreateKeyValues>({
    name: '',
    guardrail_enabled: true,
    store_full_messages: false,
  })
  const { toast } = useToast()

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>创建虚拟 Key</DialogTitle>
          <DialogDescription>创建后明文仅展示一次，请立即复制保存。</DialogDescription>
        </DialogHeader>
        {plaintext ? (
          <div className="space-y-3 py-2">
            <Label className="text-xs text-muted-foreground">明文 Key（仅本次显示）</Label>
            <div className="flex items-center gap-2">
              <Input readOnly value={plaintext} className="font-mono text-xs" />
              <Button
                size="icon"
                variant="outline"
                onClick={() => {
                  void navigator.clipboard.writeText(plaintext)
                  toast({ title: '已复制' })
                }}
              >
                <Copy className="h-4 w-4" />
              </Button>
            </div>
          </div>
        ) : (
          <div className="space-y-3 py-2">
            <div>
              <Label htmlFor="key-name">名称</Label>
              <Input
                id="key-name"
                placeholder="生产环境 / SDK 客户端 / ..."
                value={values.name}
                onChange={(e) => {
                  setValues({ ...values, name: e.target.value })
                }}
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label htmlFor="rpm">每分钟请求数上限（留空不限）</Label>
                <Input
                  id="rpm"
                  type="number"
                  value={values.rpm_limit ?? ''}
                  onChange={(e) => {
                    setValues({
                      ...values,
                      rpm_limit: e.target.value ? Number(e.target.value) : null,
                    })
                  }}
                />
              </div>
              <div>
                <Label htmlFor="tpm">每分钟令牌数上限（留空不限）</Label>
                <Input
                  id="tpm"
                  type="number"
                  value={values.tpm_limit ?? ''}
                  onChange={(e) => {
                    setValues({
                      ...values,
                      tpm_limit: e.target.value ? Number(e.target.value) : null,
                    })
                  }}
                />
              </div>
            </div>
            <div className="flex items-center justify-between">
              <Label htmlFor="guardrail" className="flex flex-col gap-1">
                <span>PII 守卫</span>
                <span className="text-xs text-muted-foreground">
                  脱敏手机/邮箱/身份证/银行卡/IP 等敏感数据后再请求
                </span>
              </Label>
              <Switch
                id="guardrail"
                checked={values.guardrail_enabled}
                onCheckedChange={(v) => {
                  setValues({ ...values, guardrail_enabled: v })
                }}
              />
            </div>
            <div className="flex items-center justify-between">
              <Label htmlFor="store" className="flex flex-col gap-1">
                <span>记录完整消息</span>
                <span className="text-xs text-muted-foreground">
                  关闭后仅存元数据（用于合规场景）
                </span>
              </Label>
              <Switch
                id="store"
                checked={values.store_full_messages}
                onCheckedChange={(v) => {
                  setValues({ ...values, store_full_messages: v })
                }}
              />
            </div>
          </div>
        )}
        <DialogFooter>
          {plaintext ? (
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
                variant="ghost"
                onClick={() => {
                  onOpenChange(false)
                }}
              >
                取消
              </Button>
              <Button
                onClick={() => {
                  if (!values.name) return
                  onSubmit(values)
                }}
                disabled={!values.name}
              >
                创建
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
