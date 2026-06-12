/**
 * 统一凭据工具栏：归属筛选 + 搜索 + 操作。
 */

import type React from 'react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import type { UnifiedCredentialScopeFilter } from '@/features/gateway-credentials/unified/unified-credentials-filters'
import { GatewayRefreshButton } from '@/features/gateway-shared/gateway-refresh-button'
import { Plus, Search, Upload } from '@/lib/lucide-icons'

const SCOPE_FILTER_OPTIONS: ReadonlyArray<{
  value: UnifiedCredentialScopeFilter
  label: string
  countKey: 'total' | 'personal' | 'team' | 'system'
}> = [
  { value: 'all', label: '全部', countKey: 'total' },
  { value: 'user', label: '个人', countKey: 'personal' },
  { value: 'team', label: '团队', countKey: 'team' },
  { value: 'system', label: '系统', countKey: 'system' },
]

export interface UnifiedCredentialsToolbarProps {
  search: string
  onSearchChange: (value: string) => void
  scopeFilter: UnifiedCredentialScopeFilter
  onScopeFilterChange: (value: UnifiedCredentialScopeFilter) => void
  counts: {
    personal: number
    team: number
    system: number
    total: number
  }
  filteredTotal: number
  hasActiveFilters: boolean
  isRefreshing?: boolean
  onRefresh?: () => void
  showImport?: boolean
  onImport?: () => void
  showVerify?: boolean
  verifyPending?: boolean
  onVerify?: () => void
  onAdd: () => void
}

export function UnifiedCredentialsToolbar({
  search,
  onSearchChange,
  scopeFilter,
  onScopeFilterChange,
  counts,
  filteredTotal,
  hasActiveFilters,
  isRefreshing = false,
  onRefresh,
  showImport = false,
  onImport,
  showVerify = false,
  verifyPending = false,
  onVerify,
  onAdd,
}: UnifiedCredentialsToolbarProps): React.JSX.Element {
  const countByKey = {
    total: counts.total,
    personal: counts.personal,
    team: counts.team,
    system: counts.system,
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        {SCOPE_FILTER_OPTIONS.map((option) => {
          const count = countByKey[option.countKey]
          const active = scopeFilter === option.value
          return (
            <Button
              key={option.value}
              type="button"
              size="sm"
              variant={active ? 'secondary' : 'outline'}
              className="h-7 text-xs"
              onClick={() => {
                onScopeFilterChange(option.value)
              }}
            >
              {option.label}
              <Badge variant={active ? 'outline' : 'secondary'} className="ml-1.5 font-normal">
                {count}
              </Badge>
            </Button>
          )
        })}
        {hasActiveFilters ? (
          <span className="text-xs text-muted-foreground">筛选结果 {filteredTotal} 条</span>
        ) : null}
      </div>

      <div className="flex flex-wrap items-center gap-2 sm:gap-3">
        <Badge variant="secondary" className="font-normal">
          {counts.personal} 个人 · {counts.team} 团队 · {counts.system} 系统
        </Badge>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <div className="relative min-w-[200px] max-w-xs flex-1 sm:flex-none">
            <Search className="pointer-events-none absolute left-2.5 top-2 h-4 w-4 text-muted-foreground" />
            <Input
              value={search}
              onChange={(e) => {
                onSearchChange(e.target.value)
              }}
              placeholder="名称、提供商、归属、掩码"
              className="h-8 pl-8 text-sm"
              aria-label="筛选凭据"
            />
          </div>
          {onRefresh ? (
            <GatewayRefreshButton
              isFetching={isRefreshing}
              ariaLabel="刷新凭据"
              onRefresh={onRefresh}
            />
          ) : null}
          {showImport && onImport ? (
            <Button variant="outline" size="sm" onClick={onImport}>
              <Upload className="mr-1.5 h-4 w-4" />
              导入到团队
            </Button>
          ) : null}
          {showVerify && onVerify ? (
            <Button variant="outline" size="sm" disabled={verifyPending} onClick={onVerify}>
              {verifyPending ? '验证中…' : '验证'}
            </Button>
          ) : null}
          <Button size="sm" onClick={onAdd}>
            <Plus className="mr-1.5 h-4 w-4" />
            新增
          </Button>
        </div>
      </div>
    </div>
  )
}
