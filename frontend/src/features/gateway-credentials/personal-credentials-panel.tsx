/**
 * 个人凭据（/my-credentials）列表与 CRUD，供设置页与网关凭据页复用。
 */

import { useCallback, useEffect, useMemo, useState } from 'react'
import type React from 'react'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Eye, EyeOff, ExternalLink, Key, Loader2, Pencil, Plus } from 'lucide-react'
import { Link } from 'react-router-dom'

import { gatewayApi, type ProviderCredential } from '@/api/gateway'
import { providerConfigApi } from '@/api/provider-config'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
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
import { useToast } from '@/hooks/use-toast'
import { useAuthStore } from '@/stores/auth'

import { USER_GATEWAY_CREDENTIAL_PROVIDER_IDS, credentialProviderLabel } from './constants'
import { displayListApiKeyMasked } from './mask-display'

export type PersonalCredentialsPanelLayout = 'settings' | 'gateway'

export interface PersonalCredentialsPanelProps {
  layout: PersonalCredentialsPanelLayout
}

export function PersonalCredentialsPanel({
  layout,
}: Readonly<PersonalCredentialsPanelProps>): React.ReactElement {
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const token = useAuthStore((s) => s.token)
  const hasAuthSession = Boolean(token)
  const [showFullMaskedInList, setShowFullMaskedInList] = useState(false)
  const [showKey, setShowKey] = useState(false)
  const [addOpen, setAddOpen] = useState(false)
  const [editCred, setEditCred] = useState<ProviderCredential | null>(null)
  const [formProvider, setFormProvider] = useState('openai')
  const [formName, setFormName] = useState('')
  const [formApiKey, setFormApiKey] = useState('')
  const [formApiBase, setFormApiBase] = useState('')
  const [formIsActive, setFormIsActive] = useState(true)

  const { data: credentials = [], isLoading } = useQuery({
    queryKey: ['gateway', 'my-credentials'],
    queryFn: () => gatewayApi.listMyCredentials(),
    enabled: hasAuthSession,
  })

  useEffect(() => {
    if (!hasAuthSession) {
      setShowFullMaskedInList(false)
    }
  }, [hasAuthSession])

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

  const invalidate = useCallback((): void => {
    void queryClient.invalidateQueries({ queryKey: ['gateway', 'my-credentials'] })
    void queryClient.invalidateQueries({ queryKey: ['provider-configs'] })
    void queryClient.invalidateQueries({ queryKey: ['gateway', 'credentials'] })
  }, [queryClient])

  const resetForm = useCallback((): void => {
    setFormProvider('openai')
    setFormName('')
    setFormApiKey('')
    setFormApiBase('')
    setFormIsActive(true)
    setShowKey(false)
  }, [])

  const openAdd = useCallback(
    (provider?: string): void => {
      resetForm()
      if (provider) setFormProvider(provider)
      setAddOpen(true)
    },
    [resetForm]
  )

  const openEdit = useCallback((c: ProviderCredential): void => {
    setEditCred(c)
    setFormProvider(c.provider)
    setFormName(c.name)
    setFormApiKey('')
    setFormApiBase(c.api_base ?? '')
    setFormIsActive(c.is_active)
    setShowKey(false)
  }, [])

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
      toast({ title: '凭据已添加' })
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '添加失败', description: e.message })
    },
  })

  const updateMutation = useMutation({
    mutationFn: () => {
      if (!editCred) throw new Error('no credential')
      return gatewayApi.updateMyCredential(editCred.id, {
        name: formName.trim() || editCred.name,
        ...(formApiKey.trim() ? { api_key: formApiKey.trim() } : {}),
        api_base: formApiBase.trim() || null,
        is_active: formIsActive,
      })
    },
    onSuccess: () => {
      invalidate()
      setEditCred(null)
      resetForm()
      toast({ title: '已保存' })
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '保存失败', description: e.message })
    },
  })

  const testMutation = useMutation({
    mutationFn: (provider: string) => providerConfigApi.test(provider),
    onSuccess: (data) => {
      if (data.success) toast({ title: 'Key 有效' })
      else toast({ variant: 'destructive', title: 'Key 验证失败' })
    },
    onError: (e: Error) => {
      toast({ variant: 'destructive', title: '验证失败', description: e.message })
    },
  })

  const submitAdd = (): void => {
    if (!formApiKey.trim()) {
      toast({ variant: 'destructive', title: '请输入 API Key' })
      return
    }
    createMutation.mutate()
  }

  const submitEdit = (): void => {
    if (!editCred) return
    const nameUnchanged = formName.trim() === editCred.name
    const baseUnchanged = formApiBase.trim() === (editCred.api_base ?? '').trim()
    const keyEmpty = !formApiKey.trim()
    const activeUnchanged = formIsActive === editCred.is_active
    if (keyEmpty && nameUnchanged && baseUnchanged && activeUnchanged) {
      toast({
        variant: 'destructive',
        title: '请至少修改名称、Base、启用状态或填写新 API Key',
      })
      return
    }
    updateMutation.mutate()
  }

  const outerClass = 'space-y-4'

  const headerToolbar = useMemo(
    () => (
      <div className="flex items-center gap-1">
        {layout === 'settings' ? (
          <Button variant="ghost" size="icon" asChild title="在网关打开">
            <Link to="/gateway/credentials?tab=personal">
              <ExternalLink className="h-4 w-4" />
            </Link>
          </Button>
        ) : null}
        <Button
          size="sm"
          disabled={!hasAuthSession}
          onClick={() => {
            openAdd()
          }}
        >
          <Plus className="mr-1 h-4 w-4" />
          添加
        </Button>
      </div>
    ),
    [layout, hasAuthSession, openAdd]
  )

  const credentialsBody = useMemo(
    () => (
      <>
        {hasAuthSession ? (
          <div className="flex flex-wrap items-center justify-end gap-2 border-b pb-3">
            <Label htmlFor="show-full-masked-list" className="cursor-pointer text-xs font-normal">
              显示掩码
            </Label>
            <Switch
              id="show-full-masked-list"
              checked={showFullMaskedInList}
              onCheckedChange={setShowFullMaskedInList}
              aria-label="在列表中显示完整 API Key 掩码"
            />
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">请先登录</p>
        )}
        {USER_GATEWAY_CREDENTIAL_PROVIDER_IDS.map((provider) => {
          const rows = byProvider.get(provider) ?? []
          return (
            <div key={provider} className="flex flex-col gap-3 rounded-lg border p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex min-w-0 items-center gap-2">
                  <Key className="h-4 w-4 shrink-0 text-muted-foreground" />
                  <span className="font-medium">{credentialProviderLabel(provider)}</span>
                  <Badge variant={rows.length > 0 ? 'secondary' : 'outline'}>
                    {rows.length > 0 ? rows.length : '—'}
                  </Badge>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={!hasAuthSession}
                    onClick={() => {
                      openAdd(provider)
                    }}
                  >
                    添加账号
                  </Button>
                  {rows.length > 0 ? (
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={!hasAuthSession || testMutation.isPending}
                      onClick={() => {
                        testMutation.mutate(provider)
                      }}
                    >
                      {testMutation.isPending ? '验证中…' : '验证'}
                    </Button>
                  ) : null}
                </div>
              </div>
              {rows.length > 0 ? (
                <ul className="divide-y rounded-md border">
                  {rows.map((c) => (
                    <li
                      key={c.id}
                      className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 text-sm"
                    >
                      <div className="min-w-0 flex-1">
                        <span className="font-medium">{c.name}</span>
                        <div className="mt-0.5 font-mono text-[11px] text-muted-foreground">
                          {displayListApiKeyMasked(
                            showFullMaskedInList,
                            hasAuthSession,
                            c.api_key_masked
                          )}
                        </div>
                        {c.api_base ? (
                          <span className="mt-0.5 block truncate text-muted-foreground">
                            {c.api_base}
                          </span>
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
                          disabled={!hasAuthSession}
                          onClick={() => {
                            openEdit(c)
                          }}
                          aria-label="编辑"
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                      </div>
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          )
        })}
      </>
    ),
    [hasAuthSession, showFullMaskedInList, byProvider, testMutation, openAdd, openEdit]
  )

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-12">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  return (
    <div className={outerClass}>
      {layout === 'settings' ? (
        <>
          <div className="flex flex-row items-center justify-between gap-2 border-b pb-3">
            <h3 className="text-base font-semibold tracking-tight">提供商凭据</h3>
            {headerToolbar}
          </div>
          <div className="space-y-4 pt-2">{credentialsBody}</div>
        </>
      ) : (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-base">提供商凭据</CardTitle>
            {headerToolbar}
          </CardHeader>
          <CardContent className="space-y-4">{credentialsBody}</CardContent>
        </Card>
      )}

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
                  {USER_GATEWAY_CREDENTIAL_PROVIDER_IDS.map((p) => (
                    <SelectItem key={p} value={p}>
                      {credentialProviderLabel(p)}
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
                placeholder="work / personal / default"
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
            <div className="flex items-center justify-between rounded-md border px-3 py-2">
              <Label htmlFor="my-cred-active" className="cursor-pointer font-normal">
                启用该账号
              </Label>
              <Switch
                id="my-cred-active"
                checked={formIsActive}
                onCheckedChange={setFormIsActive}
              />
            </div>
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
