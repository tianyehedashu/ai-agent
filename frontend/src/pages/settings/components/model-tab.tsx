/**
 * ModelTab - 用户模型管理标签页
 *
 * 在设置页面中提供模型 CRUD、连接测试功能。
 */

import { useState } from 'react'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2, Zap, Pencil, Loader2 } from 'lucide-react'

import { userModelApi } from '@/api/userModel'
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
import type {
  UserModel,
  CreateUserModelBody,
  UpdateUserModelBody,
  ModelType,
} from '@/types/user-model'
import { MODEL_PROVIDERS, MODEL_TYPE_LABELS } from '@/types/user-model'

const EMPTY_FORM: CreateUserModelBody = {
  display_name: '',
  provider: 'openai',
  model_id: '',
  api_key: '',
  api_base: '',
  model_types: ['text'],
}

export function ModelTab(): React.JSX.Element {
  const { toast } = useToast()
  const qc = useQueryClient()
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [form, setForm] = useState<CreateUserModelBody>({ ...EMPTY_FORM })

  const { data, isLoading } = useQuery({
    queryKey: ['user-models'],
    queryFn: () => userModelApi.list({ limit: 100 }),
  })

  const createMut = useMutation({
    mutationFn: (body: CreateUserModelBody) => userModelApi.create(body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['user-models'] })
      void qc.invalidateQueries({ queryKey: ['user-models', 'available'] })
      toast({ title: '模型已创建' })
      closeDialog()
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : String(err)
      toast({ title: '创建失败', description: msg, variant: 'destructive' })
    },
  })

  const updateMut = useMutation({
    mutationFn: ({ id, body }: { id: string; body: UpdateUserModelBody }) =>
      userModelApi.update(id, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['user-models'] })
      void qc.invalidateQueries({ queryKey: ['user-models', 'available'] })
      toast({ title: '模型已更新' })
      closeDialog()
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : String(err)
      toast({ title: '更新失败', description: msg, variant: 'destructive' })
    },
  })

  const deleteMut = useMutation({
    mutationFn: (id: string) => userModelApi.delete(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['user-models'] })
      void qc.invalidateQueries({ queryKey: ['user-models', 'available'] })
      toast({ title: '模型已删除' })
    },
  })

  const testMut = useMutation({
    mutationFn: (id: string) => userModelApi.testConnection(id),
    onSuccess: (result) => {
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

  const items: UserModel[] = data?.items ?? []

  function openCreate(): void {
    setEditingId(null)
    setForm({ ...EMPTY_FORM })
    setDialogOpen(true)
  }

  function openEdit(m: UserModel): void {
    setEditingId(m.id)
    setForm({
      display_name: m.display_name,
      provider: m.provider,
      model_id: m.model_id,
      api_key: '',
      api_base: m.api_base ?? '',
      model_types: m.model_types,
    })
    setDialogOpen(true)
  }

  function closeDialog(): void {
    setDialogOpen(false)
    setEditingId(null)
  }

  function handleSubmit(): void {
    if (!form.display_name || !form.model_id) {
      toast({ title: '请填写必填项', variant: 'destructive' })
      return
    }
    const body = { ...form }
    if (!body.api_key) delete body.api_key
    if (!body.api_base) delete body.api_base

    if (editingId) {
      updateMut.mutate({ id: editingId, body })
    } else {
      createMut.mutate(body)
    }
  }

  function toggleType(t: ModelType): void {
    const current = form.model_types ?? ['text']
    const next = current.includes(t) ? current.filter((x) => x !== t) : [...current, t]
    if (next.length === 0) return
    setForm({ ...form, model_types: next })
  }

  const isSaving = createMut.isPending || updateMut.isPending

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <div>
          <CardTitle>模型管理</CardTitle>
          <CardDescription>配置您的自定义模型，支持自带 API Key</CardDescription>
        </div>
        <Button size="sm" onClick={openCreate}>
          <Plus className="mr-1 h-4 w-4" />
          添加模型
        </Button>
      </CardHeader>

      <CardContent>
        {isLoading ? (
          <div className="flex justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : items.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            暂无自定义模型，点击「添加模型」开始配置
          </p>
        ) : (
          <div className="space-y-3">
            {items.map((m) => (
              <div key={m.id} className="flex items-center justify-between rounded-lg border p-3">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="truncate font-medium">{m.display_name}</span>
                    <Badge variant="outline" className="shrink-0 text-xs">
                      {MODEL_PROVIDERS.find((p) => p.id === m.provider)?.name ?? m.provider}
                    </Badge>
                    {m.model_types.map((t) => (
                      <Badge key={t} variant="secondary" className="shrink-0 text-xs">
                        {MODEL_TYPE_LABELS[t]}
                      </Badge>
                    ))}
                  </div>
                  <p className="mt-0.5 truncate text-xs text-muted-foreground">
                    {m.model_id}
                    {m.api_key_masked ? ` · Key: ${m.api_key_masked}` : ''}
                    {m.api_base ? ` · ${m.api_base}` : ''}
                  </p>
                </div>

                <div className="ml-2 flex shrink-0 items-center gap-1">
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

      {/* Create / Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-[480px]">
          <DialogHeader>
            <DialogTitle>{editingId ? '编辑模型' : '添加模型'}</DialogTitle>
            <DialogDescription>
              {editingId ? '修改模型配置' : '配置您的自定义模型，API Key 将加密存储'}
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
                onValueChange={(v) => {
                  setForm({ ...form, provider: v })
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
                placeholder="如 gpt-4o, deepseek-chat, qwen-max"
                value={form.model_id}
                onChange={(e) => {
                  setForm({ ...form, model_id: e.target.value })
                }}
              />
            </div>

            <div className="grid gap-1.5">
              <Label>API Key</Label>
              <Input
                type="password"
                placeholder={editingId ? '留空则保持不变' : 'sk-...'}
                value={form.api_key ?? ''}
                onChange={(e) => {
                  setForm({ ...form, api_key: e.target.value })
                }}
              />
            </div>

            <div className="grid gap-1.5">
              <Label>API Base URL</Label>
              <Input
                placeholder="留空使用默认端点"
                value={form.api_base ?? ''}
                onChange={(e) => {
                  setForm({ ...form, api_base: e.target.value })
                }}
              />
            </div>

            <div className="grid gap-1.5">
              <Label>模型类型</Label>
              <div className="flex gap-4">
                {(['text', 'image', 'image_gen', 'video'] as ModelType[]).map((t) => (
                  <label key={t} className="flex cursor-pointer items-center gap-1.5 text-sm">
                    <Checkbox
                      checked={(form.model_types ?? []).includes(t)}
                      onCheckedChange={() => {
                        toggleType(t)
                      }}
                    />
                    {MODEL_TYPE_LABELS[t]}
                  </label>
                ))}
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={closeDialog}>
              取消
            </Button>
            <Button onClick={handleSubmit} disabled={isSaving}>
              {isSaving && <Loader2 className="mr-1 h-4 w-4 animate-spin" />}
              {editingId ? '保存' : '创建'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  )
}
