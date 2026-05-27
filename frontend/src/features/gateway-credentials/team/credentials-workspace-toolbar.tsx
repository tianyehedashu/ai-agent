/**
 * 团队凭据工作区 Card 顶栏：汇总 Badge、搜索与操作组。
 */

import type React from 'react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { Plus, Search } from '@/lib/lucide-icons'

export interface CredentialsWorkspaceSummary {
  total: number
  queriedTeamCount: number
  queriedSharedTeamCount: number
  isPlatformAdmin: boolean
}

export interface CredentialsWorkspaceToolbarProps {
  teamSearch: string
  onTeamSearchChange: (value: string) => void
  summary?: CredentialsWorkspaceSummary
  canWrite: boolean
  onAdd: () => void
}

function formatSummaryBadge(summary: CredentialsWorkspaceSummary): string {
  if (summary.isPlatformAdmin) {
    return `${String(summary.queriedSharedTeamCount)} 协作团队 · ${String(summary.total)} 凭据`
  }
  return `${String(summary.queriedTeamCount)} 团队 · ${String(summary.total)} 凭据`
}

export function CredentialsWorkspaceToolbar({
  teamSearch,
  onTeamSearchChange,
  summary,
  canWrite,
  onAdd,
}: CredentialsWorkspaceToolbarProps): React.JSX.Element {
  return (
    <div className="flex flex-wrap items-center gap-2 sm:gap-3">
      {summary ? (
        <Badge variant="secondary" className="font-normal">
          {formatSummaryBadge(summary)}
        </Badge>
      ) : null}

      <div className="ml-auto flex flex-wrap items-center gap-2">
        <div className="relative min-w-[200px] max-w-xs flex-1 sm:flex-none">
          <Search className="pointer-events-none absolute left-2.5 top-2 h-4 w-4 text-muted-foreground" />
          <Input
            value={teamSearch}
            onChange={(e) => {
              onTeamSearchChange(e.target.value)
            }}
            placeholder="按团队名称或 slug 筛选"
            className="h-8 pl-8 text-sm"
            aria-label="按团队名称或 slug 筛选凭据"
          />
        </div>

        {canWrite ? (
          <Button
            size="sm"
            onClick={() => {
              onAdd()
            }}
          >
            <Plus className="mr-1.5 h-4 w-4" />
            新增
          </Button>
        ) : (
          <TooltipProvider delayDuration={200}>
            <Tooltip>
              <TooltipTrigger asChild>
                <span className="inline-flex">
                  <Button size="sm" disabled aria-label="新增团队凭据（需要团队管理员权限）">
                    <Plus className="mr-1.5 h-4 w-4" />
                    新增
                  </Button>
                </span>
              </TooltipTrigger>
              <TooltipContent>需要团队管理员或更高权限</TooltipContent>
            </Tooltip>
          </TooltipProvider>
        )}
      </div>
    </div>
  )
}
