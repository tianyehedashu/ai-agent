import type React from 'react'

import type { PlatformUserSummary } from '@/api/admin-users'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
import { platformRoleLabel } from '@/features/admin-users/platform-user-role-labels'
import { cn } from '@/lib/utils'

function formatDate(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export interface PlatformUsersTableProps {
  items: PlatformUserSummary[]
  isLoading: boolean
  onEdit: (user: PlatformUserSummary) => void
}

export function PlatformUsersTable({
  items,
  isLoading,
  onEdit,
}: PlatformUsersTableProps): React.JSX.Element {
  if (isLoading) {
    return (
      <Card>
        <CardContent className="py-10 text-center text-sm text-muted-foreground">
          加载中…
        </CardContent>
      </Card>
    )
  }

  if (items.length === 0) {
    return (
      <Card>
        <CardContent className="py-10 text-center text-sm text-muted-foreground">
          未找到匹配的用户
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardContent className="p-0">
        <ScrollArea className="w-full">
          <table className="w-full min-w-[720px] text-sm">
            <thead>
              <tr className="border-b text-left text-muted-foreground">
                <th className="px-4 py-3 font-medium">邮箱</th>
                <th className="px-4 py-3 font-medium">姓名</th>
                <th className="px-4 py-3 font-medium">角色</th>
                <th className="px-4 py-3 font-medium">状态</th>
                <th className="px-4 py-3 font-medium">注册时间</th>
                <th className="px-4 py-3 font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              {items.map((user) => (
                <tr key={user.id} className="border-b last:border-b-0">
                  <td className="px-4 py-3 font-mono text-xs sm:text-sm">{user.email}</td>
                  <td className="px-4 py-3">{user.name ?? '—'}</td>
                  <td className="px-4 py-3">
                    <Badge variant="outline">{platformRoleLabel(user.role)}</Badge>
                  </td>
                  <td className="px-4 py-3">
                    <Badge
                      variant={user.is_active ? 'secondary' : 'destructive'}
                      className={cn(!user.is_active && 'font-normal')}
                    >
                      {user.is_active ? '已启用' : '已禁用'}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 tabular-nums text-muted-foreground">
                    {formatDate(user.created_at)}
                  </td>
                  <td className="px-4 py-3">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        onEdit(user)
                      }}
                    >
                      编辑
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollArea>
      </CardContent>
    </Card>
  )
}
