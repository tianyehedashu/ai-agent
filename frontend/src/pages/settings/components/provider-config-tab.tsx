/**
 * 大模型提供商配置标签页
 *
 * 多账号：调用 Gateway ``/my-credentials``（user scope）；与旧版 ``/settings/providers`` 测试接口兼容。
 */

import { useMemo, useState } from 'react'
import type React from 'react'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Eye, EyeOff, Key, Loader2, Pencil, Plus, Trash2 } from 'lucide-react'
import { toast } from 'sonner'

import { gatewayApi, type ProviderCredential } from '@/api/gateway'
import { providerConfigApi } from '@/api/provider-config'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
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
import { PROVIDER_LABELS } from '@/types/provider-config'

const SUPPORTED_PROVIDERS = Object.keys(PROVIDER_LABELS)

export function ProviderConfigTab(): React.ReactElement {
  const queryClient = useQueryClient()
  const [showKey, setShowKey] = useState(false)
  const [addOpen, setAddOpen] = useState(false)
  const [editCred, setEditCred] = useState<ProviderCredential | null>(null)
  const [formProvider, setFormProvider] = useState('openai')
  const [formName, setFormName] = useState('')
  const [formApiKey, setFormApiKey] = useState('')
  const [formApiBase, setFormApiBase] = useState('')

  const { data: credentials = [], isLoading } = useQuery({
    queryKey: ['gateway', 'my-credentials'],
    queryFn: () => gatewayApi.listMyCredentials(),
  })

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

  const invalidate = (): void => {
    void queryClient.invalidateQueries({ queryKey: ['gateway', 'my-credentials'] })
    void queryClient.invalidateQueries({ queryKey: ['provider-configs'] })
    void queryClient.invalidateQueries({ queryKey: ['gateway', 'credentials'] })
  }

  const createMutation = useMutation({
    mutationFn: () =>
      gatewayApi.createMyCredential({
        provider: formProvider,
        name: formName.trim() || 'default',
        api_key: formApiKey.trim(),
        api_base: formApiBase.trim() || null,
      }),
    onSuccess: () => {
      invalidate()
      setAddOpen(false)
      resetForm()
      toast.success('凭据已添加')
    },
    onError: (e: Error) => {
      toast.error(`添加失败: ${e.message}`)
    },
  })

  const updateMutation = useMutation({
    mutationFn: () => {
      if (!editCred) throw new Error('no credential')
      return gatewayApi.updateMyCredential(editCred.id, {
        name: formName.trim() || editCred.name,
        ...(formApiKey.trim() ? { api_key: formApiKey.trim() } : {}),
        api_base: formApiBase.trim() || null,
      })
    },
    onSuccess: () => {
      invalidate()
      setEditCred(null)
      resetForm()
      toast.success('已保存')
    },
    onError: (e: Error) => {
      toast.error(`保存失败: ${e.message}`)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => gatewayApi.deleteMyCredential(id),
    onSuccess: () => {
      invalidate()
      toast.success('已删除')
    },
    onError: (e: Error) => {
      toast.error(`删除失败: ${e.message}`)
    },
  })

  const testMutation = useMutation({
    mutationFn: (provider: string) => providerConfigApi.test(provider),
    onSuccess: (data) => {
      if (data.success) toast.success('Key 有效')
      else toast.error('Key 验证失败')
    },
    onError: (e: Error) => {
      toast.error(`验证失败: ${e.message}`)
    },
  })

  const resetForm = (): void => {
    setFormProvider('openai')
    setFormName('')
    setFormApiKey('')
    setFormApiBase('')
    setShowKey(false)
  }

  const openAdd = (provider?: string): void => {
    resetForm()
    if (provider) setFormProvider(provider)
    setAddOpen(true)
  }

  const openEdit = (c: ProviderCredential): void => {
    setEditCred(c)
    setFormProvider(c.provider)
    setFormName(c.name)
    setFormApiKey('')
    setFormApiBase(c.api_base ?? '')
    setShowKey(false)
  }

  const submitAdd = (): void => {
    if (!formApiKey.trim()) {
      toast.error('请输入 API Key')
      return
    }
    createMutation.mutate()
  }

  const submitEdit = (): void => {
    if (!editCred) return
    const nameUnchanged = formName.trim() === editCred.name
    const baseUnchanged = formApiBase.trim() === (editCred.api_base ?? '').trim()
    const keyEmpty = !formApiKey.trim()
    if (keyEmpty && nameUnchanged && baseUnchanged) {
      toast.error('请至少修改名称、Base 或填写新 API Key')
      return
    }
    updateMutation.mutate()
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-12">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className="space-y-6 p-6">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0">
          <div>
            <CardTitle>大模型提供商凭据（多账号）</CardTitle>
            <CardDescription>
              同一提供商可保存多条命名凭据，供 Gateway 模型绑定与导入团队使用。验证 Key
              仍走设置侧测试接口（按提供商解析优先账号）。
            </CardDescription>
          </div>
          <Button
            size="sm"
            onClick={() => {
              openAdd()
            }}
          >
            <Plus className="mr-1 h-4 w-4" />
            添加凭据
          </Button>
        </CardHeader>
        <CardContent className="space-y-4">
          {SUPPORTED_PROVIDERS.map((provider) => {
            const rows = byProvider.get(provider) ?? []
            return (
              <div key={provider} className="flex flex-col gap-3 rounded-lg border p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Key className="h-4 w-4 text-muted-foreground" />
                    <span className="font-medium">{PROVIDER_LABELS[provider] ?? provider}</span>
                    <Badge variant={rows.length > 0 ? 'secondary' : 'outline'}>
                      {rows.length > 0 ? `${String(rows.length)} 条凭据` : '未配置'}
                    </Badge>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        openAdd(provider)
                      }}
                    >
                      添加账号
                    </Button>
                    {rows.length > 0 && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          testMutation.mutate(provider)
                        }}
                        disabled={testMutation.isPending}
                      >
                        {testMutation.isPending ? '验证中…' : '验证该提供商'}
                      </Button>
                    )}
                  </div>
                </div>
                {rows.length > 0 && (
                  <ul className="divide-y rounded-md border">
                    {rows.map((c) => (
                      <li
                        key={c.id}
                        className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 text-sm"
                      >
                        <div>
                          <span className="font-medium">{c.name}</span>
                          {c.api_base ? (
                            <span className="ml-2 text-muted-foreground">{c.api_base}</span>
                          ) : null}
                          {!c.is_active ? (
                            <Badge variant="outline" className="ml-2">
                              已停用
                            </Badge>
                          ) : null}
                        </div>
                        <div className="flex gap-1">
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => {
                              openEdit(c)
                            }}
                            aria-label="编辑"
                          >
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <AlertDialog>
                            <AlertDialogTrigger asChild>
                              <Button variant="ghost" size="icon" aria-label="删除">
                                <Trash2 className="h-4 w-4 text-destructive" />
                              </Button>
                            </AlertDialogTrigger>
                            <AlertDialogContent>
                              <AlertDialogHeader>
                                <AlertDialogTitle>删除凭据</AlertDialogTitle>
                                <AlertDialogDescription>
                                  确定删除「{PROVIDER_LABELS[c.provider] ?? c.provider} / {c.name}
                                  」？若仍被网关模型引用将返回 409。
                                </AlertDialogDescription>
                              </AlertDialogHeader>
                              <AlertDialogFooter>
                                <AlertDialogCancel>取消</AlertDialogCancel>
                                <AlertDialogAction
                                  className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                                  onClick={() => {
                                    deleteMutation.mutate(c.id)
                                  }}
                                >
                                  删除
                                </AlertDialogAction>
                              </AlertDialogFooter>
                            </AlertDialogContent>
                          </AlertDialog>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )
          })}
        </CardContent>
      </Card>

      <Dialog open={addOpen} onOpenChange={setAddOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>添加凭据</DialogTitle>
          </DialogHeader>
          <div className="grid gap-3 py-2">
            <div className="space-y-2">
              <Label>提供商</Label>
              <Select value={formProvider} onValueChange={setFormProvider}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {SUPPORTED_PROVIDERS.map((p) => (
                    <SelectItem key={p} value={p}>
                      {PROVIDER_LABELS[p] ?? p}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>账号名称</Label>
              <Input
                value={formName}
                onChange={(e) => {
                  setFormName(e.target.value)
                }}
                placeholder="例如 work、personal、default"
              />
            </div>
            <div className="space-y-2">
              <Label>API Key</Label>
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
                    setShowKey(!showKey)
                  }}
                >
                  {showKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </Button>
              </div>
            </div>
            <div className="space-y-2">
              <Label>API Base（可选）</Label>
              <Input
                type="url"
                value={formApiBase}
                onChange={(e) => {
                  setFormApiBase(e.target.value)
                }}
                placeholder="自定义 API 地址"
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setAddOpen(false)
              }}
            >
              取消
            </Button>
            <Button onClick={submitAdd} disabled={createMutation.isPending}>
              {createMutation.isPending ? '保存中…' : '保存'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={editCred !== null}
        onOpenChange={(o) => {
          if (!o) {
            setEditCred(null)
            resetForm()
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>编辑凭据</DialogTitle>
          </DialogHeader>
          <div className="grid gap-3 py-2">
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
              <Label>新 API Key（留空则不变）</Label>
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
                    setShowKey(!showKey)
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
    </div>
  )
}
