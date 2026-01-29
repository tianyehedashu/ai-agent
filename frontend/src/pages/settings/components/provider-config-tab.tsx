/**
 * 大模型提供商配置标签页
 *
 * 配置/测试各提供商的 API Key（用户 Key 优先于系统 Key，不计入配额）
 */

import { useState } from 'react'
import type React from 'react'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Eye, EyeOff, Key, Loader2, Trash2 } from 'lucide-react'
import { toast } from 'sonner'

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
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import type { ProviderConfig } from '@/types/provider-config'
import { PROVIDER_LABELS } from '@/types/provider-config'

const SUPPORTED_PROVIDERS = Object.keys(PROVIDER_LABELS)

export function ProviderConfigTab(): React.ReactElement {
  const queryClient = useQueryClient()
  const [editingProvider, setEditingProvider] = useState<string | null>(null)
  const [apiKey, setApiKey] = useState('')
  const [apiBase, setApiBase] = useState('')
  const [showKey, setShowKey] = useState(false)

  const { data: configs = [], isLoading } = useQuery({
    queryKey: ['provider-configs'],
    queryFn: () => providerConfigApi.list(),
  })

  const updateMutation = useMutation({
    mutationFn: ({ provider, api_key, api_base }: { provider: string; api_key: string; api_base?: string | null }) =>
      providerConfigApi.update(provider, { api_key, api_base: api_base || undefined }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['provider-configs'] }).catch(() => {})
      setEditingProvider(null)
      setApiKey('')
      setApiBase('')
      toast.success('配置已保存')
    },
    onError: (e: Error) => {
      toast.error(`保存失败: ${e.message}`)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (provider: string) => providerConfigApi.delete(provider),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['provider-configs'] }).catch(() => {})
      toast.success('配置已删除')
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

  const configByProvider = new Map<string, ProviderConfig>(
    configs.map((c) => [c.provider, c])
  )

  const startEdit = (provider: string) => {
    setEditingProvider(provider)
    setApiKey('')
    const existing = configByProvider.get(provider)
    setApiBase(existing?.api_base ?? '')
  }

  const submitEdit = () => {
    if (!editingProvider || !apiKey.trim()) {
      toast.error('请输入 API Key')
      return
    }
    updateMutation.mutate({
      provider: editingProvider,
      api_key: apiKey.trim(),
      api_base: apiBase.trim() || null,
    })
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
        <CardHeader>
          <CardTitle>大模型提供商 Key</CardTitle>
          <CardDescription>
            配置您自己的 API Key 后，将优先使用您的 Key 调用，且不计入系统配额
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {SUPPORTED_PROVIDERS.map((provider) => {
            const config = configByProvider.get(provider)
            const isEditing = editingProvider === provider

            return (
              <div
                key={provider}
                className="flex flex-col gap-2 rounded-lg border p-4"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Key className="h-4 w-4 text-muted-foreground" />
                    <span className="font-medium">
                      {PROVIDER_LABELS[provider] ?? provider}
                    </span>
                    {config ? (
                      <Badge variant="secondary">已配置</Badge>
                    ) : (
                      <Badge variant="outline">未配置</Badge>
                    )}
                  </div>
                  {!isEditing && (
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => { startEdit(provider); }}
                      >
                        {config ? '更新 Key' : '配置 Key'}
                      </Button>
                      {config && (
                        <>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => { testMutation.mutate(provider); }}
                            disabled={testMutation.isPending}
                          >
                            {testMutation.isPending ? '验证中…' : '验证 Key'}
                          </Button>
                          <AlertDialog>
                            <AlertDialogTrigger asChild>
                              <Button variant="ghost" size="sm">
                                <Trash2 className="h-4 w-4 text-destructive" />
                              </Button>
                            </AlertDialogTrigger>
                            <AlertDialogContent>
                              <AlertDialogHeader>
                                <AlertDialogTitle>删除配置</AlertDialogTitle>
                                <AlertDialogDescription>
                                  确定要删除 {PROVIDER_LABELS[provider]} 的 Key
                                  配置吗？删除后将使用系统 Key 并受配额限制。
                                </AlertDialogDescription>
                              </AlertDialogHeader>
                              <AlertDialogFooter>
                                <AlertDialogCancel>取消</AlertDialogCancel>
                                <AlertDialogAction
                                  className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                                  onClick={() => { deleteMutation.mutate(provider); }}
                                >
                                  删除
                                </AlertDialogAction>
                              </AlertDialogFooter>
                            </AlertDialogContent>
                          </AlertDialog>
                        </>
                      )}
                    </div>
                  )}
                </div>

                {isEditing && (
                  <div className="mt-2 grid gap-2 sm:grid-cols-[1fr,auto]">
                    <div className="space-y-2">
                      <Label>API Key</Label>
                      <div className="relative flex gap-2">
                        <Input
                          type={showKey ? 'text' : 'password'}
                          value={apiKey}
                          onChange={(e) => { setApiKey(e.target.value); }}
                          placeholder="输入 API Key（保存后加密存储）"
                          className="pr-10"
                        />
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="absolute right-1 top-1/2 h-8 w-8 -translate-y-1/2"
                          onClick={() => { setShowKey(!showKey); }}
                        >
                          {showKey ? (
                            <EyeOff className="h-4 w-4" />
                          ) : (
                            <Eye className="h-4 w-4" />
                          )}
                        </Button>
                      </div>
                    </div>
                    <div className="space-y-2">
                      <Label>API Base（可选）</Label>
                      <Input
                        type="url"
                        value={apiBase}
                        onChange={(e) => { setApiBase(e.target.value); }}
                        placeholder="自定义 API 地址"
                      />
                    </div>
                    <div className="flex gap-2 sm:col-span-2">
                      <Button
                        onClick={submitEdit}
                        disabled={updateMutation.isPending || !apiKey.trim()}
                      >
                        {updateMutation.isPending ? '保存中…' : '保存'}
                      </Button>
                      <Button
                        variant="outline"
                        onClick={() => {
                          setEditingProvider(null)
                          setApiKey('')
                          setApiBase('')
                        }}
                      >
                        取消
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </CardContent>
      </Card>
    </div>
  )
}
