/**
 * API Key 管理标签页
 */

import { lazy, Suspense, useCallback, useMemo, useState } from 'react'
import type React from 'react'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Check, Copy, Key, Plus } from 'lucide-react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'

import { apiKeyApi } from '@/api/api-key'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  resolveGatewayTeamLabel,
  useGatewayTeamNameMap,
} from '@/features/api-key-gateway/use-gateway-teams'
import { useUserStore } from '@/stores/user'

import { ApiKeyCard } from './api-key-card'

const ApiKeyCreateDialog = lazy(async () => {
  const mod = await import('./api-key-create-dialog')
  return { default: mod.ApiKeyCreateDialog }
})
const ApiKeyEditDialog = lazy(async () => {
  const mod = await import('./api-key-edit-dialog')
  return { default: mod.ApiKeyEditDialog }
})
const ApiKeyUsageLogsDialog = lazy(async () => {
  const mod = await import('./api-key-usage-logs-dialog')
  return { default: mod.ApiKeyUsageLogsDialog }
})

const PAGE_SIZE = 20

const apiKeyListSkeleton = (
  <div className="space-y-4">
    {[0, 1, 2].map((index) => (
      <Card key={index}>
        <CardHeader>
          <div className="h-6 w-40 animate-pulse rounded bg-muted" />
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="h-10 animate-pulse rounded bg-muted" />
          <div className="h-4 w-2/3 animate-pulse rounded bg-muted" />
        </CardContent>
      </Card>
    ))}
  </div>
)

export function ApiKeyTab(): React.ReactElement {
  const queryClient = useQueryClient()
  const isAuthenticated = useUserStore((state) => state.currentUser !== null)
  const teamNameById = useGatewayTeamNameMap(isAuthenticated)

  const [createDialogOpen, setCreateDialogOpen] = useState(false)
  const [editKeyId, setEditKeyId] = useState<string | null>(null)
  const [page, setPage] = useState(0)
  const [selectedKeyId, setSelectedKeyId] = useState<string | null>(null)
  const [viewKeyId, setViewKeyId] = useState<string | null>(null)
  const [fullKey, setFullKey] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  const { data: apiKeys = [], isLoading } = useQuery({
    queryKey: ['api-keys', page],
    queryFn: () => apiKeyApi.list({ skip: page * PAGE_SIZE, limit: PAGE_SIZE }),
    enabled: isAuthenticated,
  })

  const editKey = useMemo(
    () => (editKeyId ? (apiKeys.find((key) => key.id === editKeyId) ?? null) : null),
    [apiKeys, editKeyId]
  )

  const resolveTeamLabel = useCallback(
    (teamId: string) => resolveGatewayTeamLabel(teamNameById, teamId),
    [teamNameById]
  )

  const invalidateApiKeys = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ['api-keys'] })
  }, [queryClient])

  const deleteMutation = useMutation({
    mutationFn: (id: string) => apiKeyApi.delete(id),
    onSuccess: () => {
      invalidateApiKeys()
      toast.success('API Key 已删除')
    },
    onError: (error: Error) => {
      toast.error(`删除失败: ${error.message}`)
    },
  })

  const revokeMutation = useMutation({
    mutationFn: (id: string) => apiKeyApi.revoke(id),
    onSuccess: () => {
      invalidateApiKeys()
      toast.success('API Key 已撤销')
    },
    onError: (error: Error) => {
      toast.error(`撤销失败: ${error.message}`)
    },
  })

  const toggleActiveMutation = useMutation({
    mutationFn: ({ id, isActive }: { id: string; isActive: boolean }) =>
      apiKeyApi.update(id, { is_active: isActive }),
    onSuccess: invalidateApiKeys,
  })

  const revealMutation = useMutation({
    mutationFn: (id: string) => apiKeyApi.reveal(id),
    onSuccess: (data) => {
      setFullKey(data.api_key)
    },
    onError: (error: Error) => {
      toast.error(`获取完整密钥失败: ${error.message}`)
      setViewKeyId(null)
    },
  })

  const handleEdit = useCallback((id: string) => {
    setEditKeyId(id)
  }, [])

  const handleToggleActive = useCallback(
    (id: string, isActive: boolean) => {
      toggleActiveMutation.mutate({ id, isActive })
    },
    [toggleActiveMutation]
  )

  const handleViewLogs = useCallback((id: string) => {
    setSelectedKeyId(id)
  }, [])

  const handleRevoke = useCallback(
    (id: string) => {
      revokeMutation.mutate(id)
    },
    [revokeMutation]
  )

  const handleDelete = useCallback(
    (id: string) => {
      deleteMutation.mutate(id)
    },
    [deleteMutation]
  )

  const handleRevealKey = useCallback(
    (id: string) => {
      setViewKeyId(id)
      setFullKey(null)
      revealMutation.mutate(id)
    },
    [revealMutation]
  )

  if (!isAuthenticated) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>API Key 管理</CardTitle>
          <CardDescription>登录后可创建与管理平台 API Key</CardDescription>
        </CardHeader>
        <CardContent>
          <Button asChild>
            <Link to="/login">登录</Link>
          </Button>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">API Key 管理</h2>
          <p className="text-muted-foreground">
            管理平台 sk-* 密钥；Gateway 调用见{' '}
            <Link to="/gateway/guide" className="text-primary hover:underline">
              调用指南
            </Link>
            ，虚拟 Key 见{' '}
            <Link to="/gateway/keys" className="text-primary hover:underline">
              AI 网关 · 虚拟 Key
            </Link>
          </p>
        </div>
        <Button
          onClick={() => {
            setCreateDialogOpen(true)
          }}
        >
          <Plus className="mr-2 h-4 w-4" />
          创建 API Key
        </Button>
      </div>

      {createDialogOpen ? (
        <Suspense fallback={null}>
          <ApiKeyCreateDialog
            open={createDialogOpen}
            onOpenChange={setCreateDialogOpen}
            onSuccess={invalidateApiKeys}
          />
        </Suspense>
      ) : null}

      {editKeyId ? (
        <Suspense fallback={null}>
          <ApiKeyEditDialog
            apiKey={editKey}
            open
            onOpenChange={(open) => {
              if (!open) setEditKeyId(null)
            }}
            onSuccess={invalidateApiKeys}
          />
        </Suspense>
      ) : null}

      <div className="space-y-4">
        {isLoading ? (
          apiKeyListSkeleton
        ) : apiKeys.length === 0 ? (
          <Card>
            <CardContent className="flex flex-col items-center justify-center py-12">
              <Key className="mb-4 h-12 w-12 text-muted-foreground" />
              <p className="text-muted-foreground">暂无 API Key</p>
              <p className="mt-2 text-sm text-muted-foreground">
                创建 API Key 以通过 API 访问您的资源
              </p>
            </CardContent>
          </Card>
        ) : (
          apiKeys.map((apiKey) => (
            <ApiKeyCard
              key={apiKey.id}
              apiKey={apiKey}
              resolveTeamLabel={resolveTeamLabel}
              onEdit={handleEdit}
              onToggleActive={handleToggleActive}
              onViewLogs={handleViewLogs}
              onRevoke={handleRevoke}
              onDelete={handleDelete}
              onRevealKey={handleRevealKey}
            />
          ))
        )}
      </div>

      <div className="flex items-center justify-between">
        <Button
          variant="outline"
          size="sm"
          disabled={page === 0 || isLoading}
          onClick={() => {
            setPage((p) => Math.max(0, p - 1))
          }}
        >
          上一页
        </Button>
        <span className="text-sm text-muted-foreground">第 {page + 1} 页</span>
        <Button
          variant="outline"
          size="sm"
          disabled={isLoading || apiKeys.length < PAGE_SIZE}
          onClick={() => {
            setPage((p) => p + 1)
          }}
        >
          下一页
        </Button>
      </div>

      {selectedKeyId ? (
        <Suspense fallback={null}>
          <ApiKeyUsageLogsDialog
            apiKeyId={selectedKeyId}
            open
            onOpenChange={(open) => {
              if (!open) setSelectedKeyId(null)
            }}
          />
        </Suspense>
      ) : null}

      {viewKeyId ? (
        <Dialog
          open
          onOpenChange={(open) => {
            if (!open) {
              setViewKeyId(null)
              setFullKey(null)
              setCopied(false)
            }
          }}
        >
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle>完整的 API Key</DialogTitle>
              <DialogDescription>请妥善保管您的 API Key</DialogDescription>
            </DialogHeader>

            <div className="space-y-4">
              {fullKey ? (
                <>
                  <div className="rounded-lg bg-muted p-4">
                    <div className="flex items-center justify-between gap-2">
                      <code className="flex-1 break-all font-mono text-sm">{fullKey}</code>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="shrink-0"
                        onClick={() => {
                          void navigator.clipboard.writeText(fullKey)
                          setCopied(true)
                          setTimeout(() => {
                            setCopied(false)
                          }, 2000)
                          toast.success('已复制到剪贴板')
                        }}
                      >
                        {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                      </Button>
                    </div>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    请将此密钥保存在安全的地方。关闭此对话框后，您仍可再次查看。
                  </p>
                </>
              ) : (
                <div className="rounded-lg border border-dashed p-6 text-center">
                  <div className="mx-auto mb-4 h-6 w-6 animate-pulse rounded-full border-2 border-primary border-t-transparent" />
                  <p className="text-sm text-muted-foreground">正在解密 API Key...</p>
                </div>
              )}

              <div className="flex justify-end">
                <Button
                  variant="outline"
                  onClick={() => {
                    setViewKeyId(null)
                    setFullKey(null)
                    setCopied(false)
                  }}
                >
                  关闭
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      ) : null}
    </div>
  )
}
