/**
 * AI Gateway · 虚拟 Key 管理
 */

import { useMemo, useState } from 'react'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { gatewayApi, type EntitlementPlan, type VirtualKey } from '@/api/gateway'
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
import { Checkbox } from '@/components/ui/checkbox'
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
import { useKeysEntitlementsMap } from '@/features/gateway-keys/use-keys-entitlements'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { useGatewayTeamId } from '@/hooks/use-gateway-team-id'
import { useToast } from '@/hooks/use-toast'
import { guardrailStatusLabel } from '@/lib/gateway-pii-guardrail'
import { BookOpen, Copy, Plus, Trash2 } from '@/lib/lucide-icons'

export default function GatewayKeysPage(): React.JSX.Element {
  const teamId = useGatewayTeamId()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const { isMember, isPlatformViewer } = useGatewayPermission()
  const canManageKeys = isMember && !isPlatformViewer
  const [open, setOpen] = useState(false)
  const [createdKey, setCreatedKey] = useState<string | null>(null)
  const [createdKeyId, setCreatedKeyId] = useState<string | null>(null)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [batchRevokeOpen, setBatchRevokeOpen] = useState(false)

  const { data: keys, isLoading } = useQuery({
    queryKey: ['gateway', 'keys', teamId],
    queryFn: () => gatewayApi.listKeys(teamId),
  })

  const { data: gatewayFeatures } = useQuery({
    queryKey: ['gateway', 'features', teamId],
    queryFn: () => gatewayApi.getFeatures(teamId),
    staleTime: 5 * 60 * 1000,
  })
  const piiGuardrailGloballyEnabled = gatewayFeatures?.pii_guardrail_globally_enabled ?? false

  const visibleKeys = useMemo(() => (keys ?? []).filter((k) => !k.is_system && k.is_active), [keys])
  const visibleVkeyIds = useMemo(() => visibleKeys.map((k) => k.id), [visibleKeys])
  const { activeByVkeyId, isLoadingByVkeyId } = useKeysEntitlementsMap(teamId, visibleVkeyIds)
  const allSelectableSelected =
    visibleKeys.length > 0 && visibleKeys.every((k) => selectedIds.has(k.id))
  const someSelectableSelected = visibleKeys.some((k) => selectedIds.has(k.id))

  const createMutation = useMutation({
    mutationFn: (body: Parameters<typeof gatewayApi.createKey>[1]) =>
      gatewayApi.createKey(teamId, body),
    onSuccess: (created) => {
      setCreatedKey(created.plain_key)
      setCreatedKeyId(created.id)
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'keys'] })
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '创建失败', description: e.message })
    },
  })

  const revokeMutation = useMutation({
    mutationFn: (id: string) => gatewayApi.revokeKey(teamId, id),
    onSuccess: (_result, id) => {
      queryClient.setQueryData<VirtualKey[]>(['gateway', 'keys'], (prev) =>
        (prev ?? []).filter((k) => k.id !== id)
      )
      setSelectedIds((prev) => {
        if (!prev.has(id)) return prev
        const next = new Set(prev)
        next.delete(id)
        return next
      })
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'keys'] })
      toast({ title: '已撤销' })
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '撤销失败', description: e.message })
    },
  })

  const batchRevokeMutation = useMutation({
    mutationFn: (ids: string[]) => gatewayApi.revokeKeysBatch(teamId, ids),
    onSuccess: (result) => {
      const revokedSet = new Set(result.revoked)
      queryClient.setQueryData<VirtualKey[]>(['gateway', 'keys'], (prev) =>
        (prev ?? []).filter((k) => !revokedSet.has(k.id))
      )
      setSelectedIds(new Set(result.failed.map((item) => item.key_id)))
      void queryClient.invalidateQueries({ queryKey: ['gateway', 'keys'] })
      setBatchRevokeOpen(false)
      if (result.failed.length === 0) {
        toast({ title: `已撤销 ${String(result.revoked.length)} 个虚拟 Key` })
        return
      }
      toast({
        variant: 'destructive',
        title: '部分撤销失败',
        description: `成功 ${String(result.revoked.length)} 个，失败 ${String(result.failed.length)} 个`,
      })
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '批量撤销失败', description: e.message })
    },
  })

  const toggleSelectAll = (checked: boolean): void => {
    if (checked) {
      setSelectedIds(new Set(visibleKeys.map((k) => k.id)))
      return
    }
    setSelectedIds(new Set())
  }

  const toggleSelect = (id: string, checked: boolean): void => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (checked) next.add(id)
      else next.delete(id)
      return next
    })
  }

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
            创建带 <span className="font-mono">gateway:proxy</span> 作用域的
            Key；共享团队调用仍建议使用此处的 <span className="font-mono">sk-gw-*</span>。
          </p>
        </div>
        {canManageKeys && (
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

      {canManageKeys && selectedIds.size > 0 ? (
        <div className="flex items-center justify-between rounded-md border bg-muted/30 px-4 py-2">
          <span className="text-sm text-muted-foreground">已选 {selectedIds.size} 项</span>
          <Button
            size="sm"
            variant="destructive"
            onClick={() => {
              setBatchRevokeOpen(true)
            }}
          >
            <Trash2 className="mr-1.5 h-4 w-4" />
            批量撤销
          </Button>
        </div>
      ) : null}

      <Card>
        <CardContent className="p-0">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/30 text-xs uppercase text-muted-foreground">
              <tr>
                {canManageKeys ? (
                  <th className="w-10 px-4 py-2 text-left font-medium">
                    <Checkbox
                      checked={
                        allSelectableSelected
                          ? true
                          : someSelectableSelected
                            ? 'indeterminate'
                            : false
                      }
                      disabled={visibleKeys.length === 0}
                      aria-label="全选可用虚拟 Key"
                      onCheckedChange={(checked) => {
                        toggleSelectAll(checked === true)
                      }}
                    />
                  </th>
                ) : null}
                <th className="px-4 py-2 text-left font-medium">名称</th>
                <th className="px-4 py-2 text-left font-medium">Key</th>
                <th className="px-4 py-2 text-left font-medium">允许模型</th>
                <th className="px-4 py-2 text-left font-medium">每分钟请求 / 每分钟令牌</th>
                <th className="px-4 py-2 text-left font-medium">客户套餐</th>
                <th className="px-4 py-2 text-left font-medium">守卫</th>
                <th className="px-4 py-2 text-left font-medium">状态</th>
                <th className="px-4 py-2 text-left font-medium" />
              </tr>
            </thead>
            <tbody>
              {isLoading && (
                <tr>
                  <td
                    colSpan={canManageKeys ? 9 : 8}
                    className="px-4 py-6 text-center text-muted-foreground"
                  >
                    加载中...
                  </td>
                </tr>
              )}
              {!isLoading && visibleKeys.length === 0 && (
                <tr>
                  <td
                    colSpan={canManageKeys ? 9 : 8}
                    className="px-4 py-6 text-center text-muted-foreground"
                  >
                    暂无虚拟 Key
                  </td>
                </tr>
              )}
              {visibleKeys.map((k: VirtualKey) => (
                <tr key={k.id} className="border-b last:border-0 hover:bg-muted/20">
                  {canManageKeys ? (
                    <td className="px-4 py-2">
                      {k.is_active ? (
                        <Checkbox
                          checked={selectedIds.has(k.id)}
                          aria-label={`选择 ${k.name}`}
                          onCheckedChange={(checked) => {
                            toggleSelect(k.id, checked === true)
                          }}
                        />
                      ) : null}
                    </td>
                  ) : null}
                  <td className="px-4 py-2 font-medium">{k.name}</td>
                  <td className="px-4 py-2 font-mono text-xs">{k.masked_key}</td>
                  <td className="px-4 py-2 text-xs">
                    {k.allowed_models.length === 0 ? '全部' : k.allowed_models.join(', ')}
                  </td>
                  <td className="px-4 py-2 text-xs tabular-nums">
                    {`${String(k.rpm_limit ?? '∞')} / ${String(k.tpm_limit ?? '∞')}`}
                  </td>
                  <td className="px-4 py-2 text-xs">
                    <KeyEntitlementsCell
                      activePlans={activeByVkeyId.get(k.id) ?? []}
                      isLoading={isLoadingByVkeyId.get(k.id) ?? false}
                    />
                  </td>
                  <td className="px-4 py-2 text-xs">
                    {guardrailStatusLabel(k.guardrail_enabled, piiGuardrailGloballyEnabled)}
                  </td>
                  <td className="px-4 py-2 text-xs">{k.is_active ? '可用' : '已撤销'}</td>
                  <td className="px-4 py-2">
                    <div className="flex items-center gap-1">
                      {k.is_active ? (
                        <Button variant="ghost" size="icon" className="h-7 w-7" asChild>
                          <Link
                            to={`/gateway/guide?key_id=${k.id}#clients`}
                            aria-label={`${k.name} 调用指南`}
                          >
                            <BookOpen className="h-3.5 w-3.5" />
                          </Link>
                        </Button>
                      ) : null}
                      {canManageKeys && k.is_active ? (
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
                      ) : null}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>

      <CreateKeyDialog
        open={open}
        piiGuardrailGloballyEnabled={piiGuardrailGloballyEnabled}
        onOpenChange={(v) => {
          setOpen(v)
          if (!v) {
            setCreatedKey(null)
            setCreatedKeyId(null)
          }
        }}
        createdKeyId={createdKeyId}
        onSubmit={(values) => {
          createMutation.mutate(values)
        }}
        plaintext={createdKey}
      />

      <AlertDialog open={batchRevokeOpen} onOpenChange={setBatchRevokeOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>批量撤销虚拟 Key</AlertDialogTitle>
            <AlertDialogDescription>
              确定撤销已选的 {selectedIds.size} 个虚拟 Key？撤销后对应 Key 将无法继续调用。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={batchRevokeMutation.isPending}>取消</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              disabled={batchRevokeMutation.isPending || selectedIds.size === 0}
              onClick={() => {
                batchRevokeMutation.mutate([...selectedIds])
              }}
            >
              {batchRevokeMutation.isPending ? '撤销中…' : '确认撤销'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}

function KeyEntitlementsCell({
  activePlans,
  isLoading,
}: Readonly<{
  activePlans: EntitlementPlan[]
  isLoading: boolean
}>): React.JSX.Element {
  if (isLoading) return <span className="text-muted-foreground">加载中…</span>
  const active = activePlans
  if (active.length === 0) return <span className="text-muted-foreground">未配置</span>
  return (
    <div className="flex flex-wrap gap-1">
      {active.slice(0, 2).map((plan) => (
        <Badge key={plan.id} variant="secondary" className="max-w-40 truncate">
          {plan.label}
        </Badge>
      ))}
      {active.length > 2 ? <Badge variant="outline">+{active.length - 2}</Badge> : null}
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
  piiGuardrailGloballyEnabled,
  onOpenChange,
  onSubmit,
  plaintext,
  createdKeyId,
}: Readonly<{
  open: boolean
  piiGuardrailGloballyEnabled: boolean
  onOpenChange: (v: boolean) => void
  onSubmit: (v: CreateKeyValues) => void
  plaintext: string | null
  createdKeyId: string | null
}>): React.JSX.Element {
  const [values, setValues] = useState<CreateKeyValues>({
    name: '',
    guardrail_enabled: false,
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
            {createdKeyId ? (
              <Button variant="outline" className="w-full" asChild>
                <Link
                  to={`/gateway/guide?key_id=${createdKeyId}#clients`}
                  state={{ vkeyPlain: plaintext, vkeyId: createdKeyId }}
                >
                  打开调用指南
                </Link>
              </Button>
            ) : null}
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
                  {piiGuardrailGloballyEnabled
                    ? '脱敏手机/邮箱/身份证/银行卡/IP 等敏感数据后再请求'
                    : '即将推出：脱敏手机/邮箱/身份证/银行卡/IP 等敏感数据后再请求（当前不生效）'}
                </span>
              </Label>
              <Switch
                id="guardrail"
                checked={piiGuardrailGloballyEnabled && values.guardrail_enabled}
                disabled={!piiGuardrailGloballyEnabled}
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
                  onSubmit({
                    ...values,
                    guardrail_enabled: piiGuardrailGloballyEnabled
                      ? values.guardrail_enabled
                      : false,
                  })
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
