import type React from 'react'

import { Loader2 } from 'lucide-react'

import type { TeamInviteCandidate } from '@/api/gateway/teams'
import { Checkbox } from '@/components/ui/checkbox'
import { TeamInviteCandidateRow } from '@/features/gateway-teams/team-invite-candidate-row'

export interface TeamInviteCandidateListProps {
  items: readonly TeamInviteCandidate[]
  selectedIds: ReadonlySet<string>
  isLoading: boolean
  submitDisabled?: boolean
  onSelectChange: (userId: string, checked: boolean) => void
  onSelectAllPage: (checked: boolean) => void
}

export function TeamInviteCandidateList({
  items,
  selectedIds,
  isLoading,
  submitDisabled = false,
  onSelectChange,
  onSelectAllPage,
}: TeamInviteCandidateListProps): React.JSX.Element {
  const pageIds = items.map((item) => item.id)
  const allPageSelected = pageIds.length > 0 && pageIds.every((id) => selectedIds.has(id))
  const somePageSelected = pageIds.some((id) => selectedIds.has(id))

  if (isLoading) {
    return (
      <div className="space-y-2 py-2">
        {Array.from({ length: 5 }, (_, i) => (
          <div key={i} className="h-12 animate-pulse rounded-md bg-muted" />
        ))}
      </div>
    )
  }

  if (items.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        没有可添加的用户。请调整搜索条件，或确认团队的「可发现范围」设置。
      </p>
    )
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-1">
      <div className="flex items-center gap-2 border-b px-1 py-2 text-xs text-muted-foreground">
        <Checkbox
          checked={allPageSelected ? true : somePageSelected ? 'indeterminate' : false}
          disabled={submitDisabled}
          aria-label="全选本页"
          onCheckedChange={(checked) => {
            onSelectAllPage(checked === true)
          }}
        />
        <span>全选本页</span>
      </div>
      <div className="min-h-0 flex-1 space-y-1 overflow-y-auto pr-1">
        {items.map((candidate) => (
          <TeamInviteCandidateRow
            key={candidate.id}
            candidate={candidate}
            selected={selectedIds.has(candidate.id)}
            disabled={submitDisabled}
            onSelectChange={onSelectChange}
          />
        ))}
      </div>
    </div>
  )
}

export function TeamInviteCandidateListLoading(): React.JSX.Element {
  return (
    <div className="flex flex-1 items-center justify-center py-12 text-sm text-muted-foreground">
      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
      加载用户列表…
    </div>
  )
}
