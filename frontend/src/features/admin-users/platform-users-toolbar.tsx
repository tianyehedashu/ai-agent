import type React from 'react'

import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { GatewayRefreshButton } from '@/features/gateway-shared/gateway-refresh-button'
import { Search } from '@/lib/lucide-icons'

export interface PlatformUsersToolbarProps {
  search: string
  onSearchChange: (value: string) => void
  role: string
  onRoleChange: (value: string) => void
  isActive: string
  onIsActiveChange: (value: string) => void
  total?: number
  isRefreshing?: boolean
  onRefresh?: () => void
}

export function PlatformUsersToolbar({
  search,
  onSearchChange,
  role,
  onRoleChange,
  isActive,
  onIsActiveChange,
  total,
  isRefreshing = false,
  onRefresh,
}: PlatformUsersToolbarProps): React.JSX.Element {
  return (
    <div className="flex flex-wrap items-center gap-2 sm:gap-3">
      {total !== undefined ? (
        <Badge variant="secondary" className="font-normal">
          共 {total} 位用户
        </Badge>
      ) : null}

      <div className="ml-auto flex flex-wrap items-center gap-2">
        <div className="relative min-w-[200px] max-w-xs flex-1 sm:flex-none">
          <Search className="pointer-events-none absolute left-2.5 top-2 h-4 w-4 text-muted-foreground" />
          <Input
            value={search}
            onChange={(e) => {
              onSearchChange(e.target.value)
            }}
            placeholder="搜索邮箱或姓名"
            className="h-8 pl-8 text-sm"
            aria-label="搜索用户"
          />
        </div>

        <Select value={role} onValueChange={onRoleChange}>
          <SelectTrigger className="h-8 w-[130px] text-sm" aria-label="按角色筛选">
            <SelectValue placeholder="角色" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部角色</SelectItem>
            <SelectItem value="admin">平台管理员</SelectItem>
            <SelectItem value="user">普通用户</SelectItem>
            <SelectItem value="viewer">只读账号</SelectItem>
          </SelectContent>
        </Select>

        <Select value={isActive} onValueChange={onIsActiveChange}>
          <SelectTrigger className="h-8 w-[120px] text-sm" aria-label="按状态筛选">
            <SelectValue placeholder="状态" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部状态</SelectItem>
            <SelectItem value="active">已启用</SelectItem>
            <SelectItem value="inactive">已禁用</SelectItem>
          </SelectContent>
        </Select>

        {onRefresh ? (
          <GatewayRefreshButton
            isFetching={isRefreshing}
            ariaLabel="刷新用户列表"
            onRefresh={onRefresh}
          />
        ) : null}
      </div>
    </div>
  )
}
