/**
 * 个人模型（/my-models）面板，用于 AI Gateway 模型页「个人」Tab。
 */

import { useCallback, useMemo, useState } from 'react'
import type React from 'react'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2, Pencil, Plus, Trash2, Zap } from 'lucide-react'
import { Link } from 'react-router-dom'

import { gatewayApi, type PersonalGatewayModel } from '@/api/gateway'
import { ModelStatusBadge } from '@/components/model-status-badge'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useToast } from '@/hooks/use-toast'
import { PROVIDER_CHANNEL_FILTER_HINT_LONG } from '@/lib/provider-channel-hint'
import { useAuthStore } from '@/stores/auth'
import type { ModelType } from '@/types/user-model'
import { MODEL_PROVIDERS, MODEL_TYPE_LABELS } from '@/types/user-model'

const LIST_CHANNEL_ALL = '__all__'
const NO_CREDENTIAL = '__none__'

interface PersonalModelForm {
  display_name: string
  provider: string
  model_id: string
  credential_id: string
  model_types: ModelType[]
}

const EMPTY_FORM: PersonalModelForm = {
  display_name: '',
  provider: 'openai',
  model_id: '',
  credential_id: '',
  model_types: ['text'],
}

export function PersonalModelsPanel(): React.ReactElement {
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const token = useAuthStore((s) => s.token)
  const hasAuthSession = Boolean(token)

  const [dialogOpen, setDialogOpen] = useState(false)
  const [editing, setEditing] = useState<PersonalGatewayModel | null>(null)
  const [form, setForm] = useState<PersonalModelForm>({ ...EMPTY_FORM })
  const [listChannel, setListChannel] = useState<string>(LIST_CHANNEL_ALL)

  const { data: credentials = [] } = useQuery({
    queryKey: ['gateway', 'my-credentials'],
    queryFn: () => gatewayApi.listMyCredentials(),
    enabled: hasAuthSession,
  })

  const activeCredentials = useMemo(() => credentials.filter((c) => c.is_active), [credentials])

  const { data: items = [], isLoading } = useQuery({
    queryKey: ['gateway', 'my-models', listChannel],
    queryFn: () =>
      gatewayApi.listMyModels({
        provider: listChannel === LIST_CHANNEL_ALL ? undefined : listChannel,
      }),
    enabled: hasAuthSession,
  })

  const invalidate = useCallback((): void => {
    void queryClient.invalidateQueries({ queryKey: ['gateway', 'my-models'] })
    void queryClient.invalidateQueries({ queryKey: ['gateway-models-available'] })
  }, [queryClient])

  const createMut = useMutation({
    mutationFn: gatewayApi.createMyModel,
    onSuccess: () => {
      invalidate()
      toast({ title: '模型已创建' })
      closeDialog()
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : String(err)
      toast({ title: '创建失败', description: msg, variant: 'destructive' })
    },
  })

  const updateMut = useMutation({
    mutationFn: ({
      id,
      body,
    }: {
      id: string
      body: Parameters<typeof gatewayApi.updateMyModel>[1]
    }) => gatewayApi.updateMyModel(id, body),
    onSuccess: () => {
      invalidate()
      toast({ title: '模型已更新' })
      closeDialog()
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : String(err)
      toast({ title: '更新失败', description: msg, variant: 'destructive' })
    },
  })

  const deleteMut = useMutation({
    mutationFn: gatewayApi.deleteMyModel,
    onSuccess: () => {
      invalidate()
      toast({ title: '模型已删除' })
    },
  })

  const testMut = useMutation({
    mutationFn: gatewayApi.testMyModel,
    onSuccess: (result) => {
      invalidate()
      if (result.success) {
        toast({ title: '连接成功', description: result.message })
      } else {
        toast({ title: '连接失败', description: result.message, variant: 'destructive' })
      }
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : String(err)
      toast({ title: '测试出错', description: msg, variant: 'destructive' })
    },
  })

  const credentialOptions = useMemo(() => {
    const matching = activeCredentials.filter((c) => c.provider === form.provider)
    return matching.length > 0 ? matching : activeCredentials
  }, [activeCredentials, form.provider])

  function openCreate(): void {
    setEditing(null)
    setForm({ ...EMPTY_FORM })
    setDialogOpen(true)
  }

  function openEdit(m: PersonalGatewayModel): void {
    setEditing(m)
    setForm({
      display_name: m.display_name,
      provider: m.provider,
      model_id: m.model_id,
      credential_id: m.credential_id,
      model_types: m.model_types,
    })
    setDialogOpen(true)
  }

  function closeDialog(): void {
    setDialogOpen(false)
    setEditing(null)
  }

  function handleSubmit(): void {
    if (!form.display_name || !form.model_id || !form.credential_id) {
      toast({ title: '请填写必填项并选择凭据', variant: 'destructive' })
      return
    }
    if (editing) {
      updateMut.mutate({
        id: editing.id,
        body: {
          display_name: form.display_name,
          model_id: form.model_id,
          credential_id: form.credential_id,
          is_active: editing.is_active,
        },
      })
    } else {
      createMut.mutate({
        display_name: form.display_name,
        provider: form.provider,
        model_id: form.model_id,
        credential_id: form.credential_id,
        model_types: form.model_types,
      })
    }
  }

  function toggleType(t: ModelType): void {
    if (editing) return
    const current = form.model_types
    const next = current.includes(t) ? current.filter((x) => x !== t) : [...current, t]
    if (next.length === 0) return
    setForm({ ...form, model_types: next })
  }

  const isSaving = createMut.isPending || updateMut.isPending

  if (!hasAuthSession) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-sm text-muted-foreground">
          请先登录以管理个人模型
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <div>
          <CardTitle>个人模型</CardTitle>
          <CardDescription>
            注册自带凭据的模型；请先配置{' '}
            <Link
              to="/gateway/credentials?tab=personal"
              className="text-primary underline-offset-4 hover:underline"
            >
              个人凭据
            </Link>
          </CardDescription>
        </div>
        <Button size="sm" onClick={openCreate} disabled={activeCredentials.length === 0}>
          <Plus className="mr-1 h-4 w-4" />
          添加模型
        </Button>
      </CardHeader>

      <CardContent>
        {activeCredentials.length === 0 ? (
          <p className="mb-4 text-sm text-muted-foreground">
            尚无个人凭据，请先到{' '}
            <Link
              to="/gateway/credentials?tab=personal"
              className="text-primary underline-offset-4 hover:underline"
            >
              凭据管理
            </Link>{' '}
            添加 API Key。
          </p>
        ) : null}

        <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div className="grid max-w-xs gap-1.5">
            <Label htmlFor="personal-model-channel">按接入通道筛选</Label>
            <Select
              value={listChannel}
              onValueChange={(v) => {
                setListChannel(v)
              }}
            >
              <SelectTrigger id="personal-model-channel" className="w-full sm:w-[220px]">
                <SelectValue placeholder="全部" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={LIST_CHANNEL_ALL}>全部</SelectItem>
                {MODEL_PROVIDERS.map((p) => (
                  <SelectItem key={p.id} value={p.id}>
                    {p.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">{PROVIDER_CHANNEL_FILTER_HINT_LONG}</p>
          </div>
        </div>

        {isLoading ? (
          <div className="flex justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : items.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            暂无个人模型，点击「添加模型」开始配置
          </p>
        ) : (
          <div className="space-y-3">
            {items.map((m) => (
              <div key={m.id} className="flex items-start justify-between rounded-lg border p-3">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="truncate font-medium">{m.display_name}</span>
                    <ModelStatusBadge
                      status={m.last_test_status}
                      testedAt={m.last_tested_at}
                      reason={m.last_test_reason}
                    />
                    <Badge variant="outline" className="shrink-0 text-xs">
                      {MODEL_PROVIDERS.find((p) => p.id === m.provider)?.name ?? m.provider}
                    </Badge>
                    {m.model_types.map((t) => (
                      <Badge key={t} variant="secondary" className="shrink-0 text-xs">
                        {MODEL_TYPE_LABELS[t]}
                      </Badge>
                    ))}
                  </div>
                  <p className="mt-0.5 truncate text-xs text-muted-foreground">{m.model_id}</p>
                  {m.last_test_status === 'failed' && m.last_test_reason ? (
                    <p
                      className="mt-1 line-clamp-4 text-xs text-destructive/90 [overflow-wrap:anywhere]"
                      title={m.last_test_reason}
                    >
                      {m.last_test_reason}
                    </p>
                  ) : null}
                </div>

                <div className="ml-2 flex shrink-0 items-start gap-1 pt-0.5">
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={() => {
                      testMut.mutate(m.id)
                    }}
                    disabled={testMut.isPending}
                    title="测试连接"
                  >
                    {testMut.isPending && testMut.variables === m.id ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Zap className="h-4 w-4" />
                    )}
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={() => {
                      openEdit(m)
                    }}
                    title="编辑"
                  >
                    <Pencil className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 text-destructive"
                    onClick={() => {
                      if (window.confirm(`确定删除「${m.display_name}」？此操作不可撤销。`)) {
                        deleteMut.mutate(m.id)
                      }
                    }}
                    disabled={deleteMut.isPending}
                    title="删除"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-[480px]">
          <DialogHeader>
            <DialogTitle>{editing ? '编辑模型' : '添加模型'}</DialogTitle>
            <DialogDescription>
              {editing
                ? '修改模型配置（多能力拆分为多行时仅编辑当前行）'
                : '选择已配置的个人凭据并注册模型'}
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-2">
            <div className="grid gap-1.5">
              <Label>名称 *</Label>
              <Input
                placeholder="如：我的 GPT-4o"
                value={form.display_name}
                onChange={(e) => {
                  setForm({ ...form, display_name: e.target.value })
                }}
              />
            </div>

            <div className="grid gap-1.5">
              <Label>提供商 *</Label>
              <Select
                value={form.provider}
                disabled={Boolean(editing)}
                onValueChange={(v) => {
                  setForm({ ...form, provider: v, credential_id: '' })
                }}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {MODEL_PROVIDERS.map((p) => (
                    <SelectItem key={p.id} value={p.id}>
                      {p.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="grid gap-1.5">
              <Label>模型 ID *</Label>
              <Input
                placeholder="如 gpt-4o, deepseek-chat"
                value={form.model_id}
                onChange={(e) => {
                  setForm({ ...form, model_id: e.target.value })
                }}
              />
            </div>

            <div className="grid gap-1.5">
              <Label>凭据 *</Label>
              <Select
                value={form.credential_id || NO_CREDENTIAL}
                onValueChange={(v) => {
                  setForm({ ...form, credential_id: v === NO_CREDENTIAL ? '' : v })
                }}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={NO_CREDENTIAL}>未选择</SelectItem>
                  {credentialOptions.map((c) => (
                    <SelectItem key={c.id} value={c.id}>
                      {c.name} · {c.provider}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {!editing ? (
              <div className="grid gap-1.5">
                <Label>模型类型</Label>
                <div className="flex gap-4">
                  {(['text', 'image', 'image_gen', 'video'] as ModelType[]).map((t) => (
                    <label key={t} className="flex cursor-pointer items-center gap-1.5 text-sm">
                      <Checkbox
                        checked={form.model_types.includes(t)}
                        onCheckedChange={() => {
                          toggleType(t)
                        }}
                      />
                      {MODEL_TYPE_LABELS[t]}
                    </label>
                  ))}
                </div>
              </div>
            ) : null}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={closeDialog}>
              取消
            </Button>
            <Button onClick={handleSubmit} disabled={isSaving}>
              {isSaving && <Loader2 className="mr-1 h-4 w-4 animate-spin" />}
              {editing ? '保存' : '创建'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  )
}
