/**
 * API Key 管理标签页
 */

import { useState } from 'react'
import type React from 'react'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Check, Copy, Key, Plus, Trash2, Ban, History } from 'lucide-react'
import { toast } from 'sonner'

import { apiKeyApi } from '@/api/api-key'
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
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Switch } from '@/components/ui/switch'
import { formatRelativeTime } from '@/lib/utils'
import type { ApiKey } from '@/types/api-key'
import {
  getDaysUntilExpiry,
  getScopeCategory,
  getStatusBadgeVariant,
  getStatusLabel,
} from '@/types/api-key'

import { ApiKeyCreateDialog } from './api-key-create-dialog'
import { ApiKeyUsageLogsDialog } from './api-key-usage-logs-dialog'

export function ApiKeyTab(): React.ReactElement {
  const queryClient = useQueryClient()
  const [createDialogOpen, setCreateDialogOpen] = useState(false)
  const [selectedKeyId, setSelectedKeyId] = useState<string | null>(null)
  const [viewKeyId, setViewKeyId] = useState<string | null>(null)
  const [fullKey, setFullKey] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  // 获取 API Key 列表
  const { data: apiKeys = [], isLoading } = useQuery({
    queryKey: ['api-keys'],
    queryFn: () => apiKeyApi.list(),
  })

  // 删除 API Key
  const deleteMutation = useMutation({
    mutationFn: (id: string) => apiKeyApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['api-keys'] }).catch(() => {})
      toast.success('API Key 已删除')
    },
    onError: (error: Error) => {
      toast.error(`删除失败: ${error.message}`)
    },
  })

  // 撤销 API Key
  const revokeMutation = useMutation({
    mutationFn: (id: string) => apiKeyApi.revoke(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['api-keys'] }).catch(() => {})
      toast.success('API Key 已撤销')
    },
    onError: (error: Error) => {
      toast.error(`撤销失败: ${error.message}`)
    },
  })

  // 切换状态
  const toggleActiveMutation = useMutation({
    mutationFn: ({ id, isActive }: { id: string; isActive: boolean }) =>
      apiKeyApi.update(id, { is_active: isActive }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['api-keys'] }).catch(() => {})
    },
  })

  // 解密并显示完整密钥
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

  // 处理查看完整密钥
  const handleViewFullKey = (id: string) => {
    setViewKeyId(id)
    setFullKey(null)
    revealMutation.mutate(id)
  }

  if (isLoading) {
    return <div className="p-6">加载中...</div>
  }

  return (
    <div className="space-y-6 p-6">
      {/* 头部 */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">API Key 管理</h2>
          <p className="text-muted-foreground">管理用于 API 访问的密钥</p>
        </div>
        <Button onClick={() => { setCreateDialogOpen(true); }}>
          <Plus className="mr-2 h-4 w-4" />
          创建 API Key
        </Button>
      </div>

      {/* 创建对话框 */}
      <ApiKeyCreateDialog
        open={createDialogOpen}
        onOpenChange={setCreateDialogOpen}
        onSuccess={() => {
          queryClient.invalidateQueries({ queryKey: ['api-keys'] }).catch(() => {})
        }}
      />

      {/* API Key 列表 */}
      <div className="space-y-4">
        {apiKeys.length === 0 ? (
          <Card>
            <CardContent className="flex flex-col items-center justify-center py-12">
              <Key className="mb-4 h-12 w-12 text-muted-foreground" />
              <p className="text-muted-foreground">暂无 API Key</p>
              <p className="mt-2 text-sm text-muted-foreground">创建 API Key 以通过 API 访问您的资源</p>
            </CardContent>
          </Card>
        ) : (
          apiKeys.map((apiKey) => (
            <ApiKeyCard
              key={apiKey.id}
              apiKey={apiKey}
              onToggleActive={(isActive) => {
                toggleActiveMutation.mutate({ id: apiKey.id, isActive })
              }}
              onViewLogs={() => { setSelectedKeyId(apiKey.id); }}
              onRevoke={() => { revokeMutation.mutate(apiKey.id); }}
              onDelete={() => { deleteMutation.mutate(apiKey.id); }}
              revealKey={(id) => {
                handleViewFullKey(id)
              }}
            />
          ))
        )}
      </div>

      {/* 使用日志对话框 */}
      {selectedKeyId && (
        <ApiKeyUsageLogsDialog
          apiKeyId={selectedKeyId}
          open={!!selectedKeyId}
          onOpenChange={(open) => {
            if (!open) setSelectedKeyId(null)
          }}
        />
      )}

      {/* 查看完整密钥对话框 */}
      {viewKeyId && (
        <Dialog open={!!viewKeyId} onOpenChange={(open) => {
          if (!open) {
            setViewKeyId(null)
            setFullKey(null)
            setCopied(false)
          }
        }}>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle>完整的 API Key</DialogTitle>
              <DialogDescription>
                请妥善保管您的 API Key
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4">
              {fullKey ? (
                <>
                  <div className="rounded-lg bg-muted p-4">
                    <div className="flex items-center justify-between gap-2">
                      <code className="flex-1 break-all text-sm font-mono">
                        {fullKey}
                      </code>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="shrink-0"
                        onClick={() => {
                          navigator.clipboard.writeText(fullKey).catch(() => {})
                          setCopied(true)
                          setTimeout(() => { setCopied(false); }, 2000)
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
                  <div className="mx-auto h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent mb-4" />
                  <p className="text-sm text-muted-foreground">
                    正在解密 API Key...
                  </p>
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
      )}
    </div>
  )
}

// API Key 卡片组件
function ApiKeyCard({
  apiKey,
  onToggleActive,
  onViewLogs,
  onRevoke,
  onDelete,
  revealKey,
}: {
  apiKey: ApiKey
  onToggleActive: (isActive: boolean) => void
  onViewLogs: () => void
  onRevoke: () => void
  onDelete: () => void
  revealKey: (id: string) => void
}): React.ReactElement {
  const daysUntilExpiry = getDaysUntilExpiry(apiKey.expires_at)
  const scopeCategories = getScopeCategory(apiKey.scopes)

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between">
          <div className="space-y-1 flex-1">
            <div className="flex items-center gap-2">
              <CardTitle className="text-lg">{apiKey.name}</CardTitle>
              <Badge variant={getStatusBadgeVariant(apiKey.status)}>{getStatusLabel(apiKey.status)}</Badge>
              {!apiKey.is_active && apiKey.status === 'active' && (
                <Badge variant="outline" className="text-muted-foreground">
                  已禁用
                </Badge>
              )}
            </div>
            {apiKey.description && <CardDescription>{apiKey.description}</CardDescription>}
          </div>
          <Switch
            checked={apiKey.is_active}
            onCheckedChange={onToggleActive}
            disabled={apiKey.status !== 'active'}
          />
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Key 显示 - 脱敏密钥 */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs text-muted-foreground">API Key（脱敏显示）</span>
            <Button
              variant="link"
              size="sm"
              className="h-auto p-0 text-xs"
              onClick={() => { revealKey(apiKey.id); }}
            >
              查看完整密钥
            </Button>
          </div>
          <code className="block w-full rounded bg-muted px-3 py-2 text-sm font-mono">
            {apiKey.masked_key}
          </code>
        </div>

        {/* 作用域标签 */}
        <div className="flex flex-wrap gap-1">
          {scopeCategories.map((category) => (
            <Badge key={category} variant="outline" className="text-xs">
              {category}
            </Badge>
          ))}
        </div>

        {/* 统计信息 */}
        <div className="flex items-center gap-4 text-sm text-muted-foreground">
          <span>使用次数: {apiKey.usage_count}</span>
          <span>
            过期时间: {daysUntilExpiry === 0 ? '今天' : daysUntilExpiry === 1 ? '明天' : `${daysUntilExpiry} 天后`}
          </span>
          {apiKey.last_used_at && <span>最后使用: {formatRelativeTime(apiKey.last_used_at)}</span>}
        </div>

        {/* 操作按钮 */}
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={onViewLogs}
          >
            <History className="mr-2 h-4 w-4" />
            查看日志
          </Button>

          {apiKey.status === 'active' && (
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button variant="outline" size="sm">
                  <Ban className="mr-2 h-4 w-4" />
                  撤销
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>撤销 API Key</AlertDialogTitle>
                  <AlertDialogDescription>
                    确定要撤销 API Key &quot;{apiKey.name}&quot; 吗？撤销后无法恢复。
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>取消</AlertDialogCancel>
                  <AlertDialogAction onClick={onRevoke}>撤销</AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          )}

          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="ghost" size="sm" className="text-destructive">
                <Trash2 className="mr-2 h-4 w-4" />
                删除
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>删除 API Key</AlertDialogTitle>
                <AlertDialogDescription>
                  确定要删除 API Key &quot;{apiKey.name}&quot; 吗？此操作无法撤销。
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>取消</AlertDialogCancel>
                <AlertDialogAction onClick={onDelete} className="bg-destructive">
                  删除
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </CardContent>
    </Card>
  )
}
