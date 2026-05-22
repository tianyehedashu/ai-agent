/**
 * API Key 列表卡片（memo 避免父级对话框状态触发全列表重渲染）
 */

import { memo } from 'react'
import type React from 'react'

import { Ban, History, Pencil, Trash2 } from 'lucide-react'

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
import { Switch } from '@/components/ui/switch'
import { ApiKeyGrantDetails } from '@/features/api-key-gateway/api-key-grant-details'
import { formatRelativeTime } from '@/lib/utils'
import type { ApiKey } from '@/types/api-key'
import {
  getDaysUntilExpiry,
  getScopeCategory,
  getStatusBadgeVariant,
  getStatusLabel,
} from '@/types/api-key'

export interface ApiKeyCardProps {
  apiKey: ApiKey
  resolveTeamLabel: (teamId: string) => string
  onEdit: (id: string) => void
  onToggleActive: (id: string, isActive: boolean) => void
  onViewLogs: (id: string) => void
  onRevoke: (id: string) => void
  onDelete: (id: string) => void
  onRevealKey: (id: string) => void
}

function ApiKeyCardComponent({
  apiKey,
  resolveTeamLabel,
  onEdit,
  onToggleActive,
  onViewLogs,
  onRevoke,
  onDelete,
  onRevealKey,
}: ApiKeyCardProps): React.ReactElement {
  const daysUntilExpiry = getDaysUntilExpiry(apiKey.expires_at)
  const scopeCategories = getScopeCategory(apiKey.scopes)
  const hasGatewayProxy = apiKey.scopes.includes('gateway:proxy')
  const canRevoke = apiKey.status === 'active' || apiKey.status === 'disabled'

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between">
          <div className="flex-1 space-y-1">
            <div className="flex items-center gap-2">
              <CardTitle className="text-lg">{apiKey.name}</CardTitle>
              <Badge variant={getStatusBadgeVariant(apiKey.status)}>
                {getStatusLabel(apiKey.status)}
              </Badge>
            </div>
            {apiKey.description ? <CardDescription>{apiKey.description}</CardDescription> : null}
          </div>
          <Switch
            checked={apiKey.is_active}
            onCheckedChange={(isActive) => {
              onToggleActive(apiKey.id, isActive)
            }}
            disabled={apiKey.status === 'revoked' || apiKey.status === 'expired'}
          />
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs text-muted-foreground">API Key（脱敏显示）</span>
            <Button
              variant="link"
              size="sm"
              className="h-auto p-0 text-xs"
              onClick={() => {
                onRevealKey(apiKey.id)
              }}
            >
              查看完整密钥
            </Button>
          </div>
          <code className="block w-full rounded bg-muted px-3 py-2 font-mono text-sm">
            {apiKey.masked_key}
          </code>
        </div>

        <div className="flex flex-wrap gap-1">
          {scopeCategories.map((category) => (
            <Badge key={category} variant="outline" className="text-xs">
              {category}
            </Badge>
          ))}
        </div>

        {hasGatewayProxy ? (
          <ApiKeyGrantDetails grants={apiKey.gateway_grants} resolveTeamLabel={resolveTeamLabel} />
        ) : null}

        <div className="flex items-center gap-4 text-sm text-muted-foreground">
          <span>使用次数: {apiKey.usage_count}</span>
          <span>
            过期时间:{' '}
            {daysUntilExpiry === 0
              ? '今天'
              : daysUntilExpiry === 1
                ? '明天'
                : `${String(daysUntilExpiry)} 天后`}
          </span>
          {apiKey.last_used_at ? (
            <span>最后使用: {formatRelativeTime(apiKey.last_used_at)}</span>
          ) : null}
        </div>

        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              onEdit(apiKey.id)
            }}
          >
            <Pencil className="mr-2 h-4 w-4" />
            编辑
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              onViewLogs(apiKey.id)
            }}
          >
            <History className="mr-2 h-4 w-4" />
            查看日志
          </Button>

          {canRevoke ? (
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
                  <AlertDialogAction
                    onClick={() => {
                      onRevoke(apiKey.id)
                    }}
                  >
                    撤销
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          ) : null}

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
                <AlertDialogAction
                  onClick={() => {
                    onDelete(apiKey.id)
                  }}
                  className="bg-destructive"
                >
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

export const ApiKeyCard = memo(ApiKeyCardComponent)
