/**
 * 平台管理 - 用户管理
 */

import { useCallback, useDeferredValue, useState } from 'react'
import type React from 'react'

import { useQueryClient } from '@tanstack/react-query'
import { Users } from 'lucide-react'

import type { PlatformRole, PlatformUserSummary } from '@/api/adminUsers'
import { PaginationControls } from '@/components/pagination-controls'
import { PlatformUserEditSheet } from '@/features/admin-users/platform-user-edit-sheet'
import { PlatformUsersTable } from '@/features/admin-users/platform-users-table'
import { PlatformUsersToolbar } from '@/features/admin-users/platform-users-toolbar'
import { PLATFORM_USERS_QUERY_KEY } from '@/features/admin-users/query-keys'
import { usePlatformUsersList } from '@/features/admin-users/use-platform-users-list'

export default function AdminUsersPage(): React.JSX.Element {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const deferredSearch = useDeferredValue(search)
  const [role, setRole] = useState<string>('all')
  const [isActive, setIsActive] = useState<string>('all')
  const [page, setPage] = useState(1)
  const [editingUserId, setEditingUserId] = useState<string | null>(null)
  const [editOpen, setEditOpen] = useState(false)

  const { data, isLoading, isFetching, refetch } = usePlatformUsersList({
    search: deferredSearch,
    role: role as PlatformRole | 'all',
    isActive: isActive as 'all' | 'active' | 'inactive',
    page,
    enabled: true,
  })

  const handleSearchChange = useCallback((value: string) => {
    setSearch(value)
    setPage(1)
  }, [])

  const handleRoleChange = useCallback((value: string) => {
    setRole(value)
    setPage(1)
  }, [])

  const handleIsActiveChange = useCallback((value: string) => {
    setIsActive(value)
    setPage(1)
  }, [])

  const handleEdit = useCallback((user: PlatformUserSummary) => {
    setEditingUserId(user.id)
    setEditOpen(true)
  }, [])

  const handleSaved = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: PLATFORM_USERS_QUERY_KEY })
  }, [queryClient])

  const handleRefresh = useCallback(() => {
    void refetch()
  }, [refetch])

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-4 sm:p-6">
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <Users className="h-6 w-6 text-muted-foreground" />
          <h1 className="text-2xl font-semibold tracking-tight">用户管理</h1>
        </div>
        <p className="text-sm text-muted-foreground">
          查看与管理平台注册用户，支持分页、筛选与资料编辑。
        </p>
      </div>

      <PlatformUsersToolbar
        search={search}
        onSearchChange={handleSearchChange}
        role={role}
        onRoleChange={handleRoleChange}
        isActive={isActive}
        onIsActiveChange={handleIsActiveChange}
        total={data?.total}
        isRefreshing={isFetching}
        onRefresh={handleRefresh}
      />

      <PlatformUsersTable items={data?.items ?? []} isLoading={isLoading} onEdit={handleEdit} />

      {data && data.total > 0 ? (
        <PaginationControls
          page={data.page}
          page_size={data.page_size}
          total={data.total}
          has_next={data.has_next}
          has_prev={data.has_prev}
          onPageChange={setPage}
        />
      ) : null}

      <PlatformUserEditSheet
        userId={editingUserId}
        open={editOpen}
        onOpenChange={setEditOpen}
        onSaved={handleSaved}
      />
    </div>
  )
}
