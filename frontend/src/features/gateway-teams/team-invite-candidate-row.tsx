import type React from 'react'

import type { TeamInviteCandidate } from '@/api/gateway/teams'
import { Checkbox } from '@/components/ui/checkbox'
import { cn } from '@/lib/utils'

export interface TeamInviteCandidateRowProps {
  candidate: TeamInviteCandidate
  selected: boolean
  disabled?: boolean
  onSelectChange: (userId: string, checked: boolean) => void
}

function displayLabel(candidate: TeamInviteCandidate): string {
  const trimmed = candidate.name?.trim()
  return trimmed && trimmed.length > 0 ? trimmed : candidate.email
}

export function TeamInviteCandidateRow({
  candidate,
  selected,
  disabled = false,
  onSelectChange,
}: TeamInviteCandidateRowProps): React.JSX.Element {
  const label = displayLabel(candidate)

  return (
    <label
      className={cn(
        'flex cursor-pointer items-start gap-3 rounded-md border px-3 py-2.5 transition-colors',
        selected ? 'border-primary/40 bg-primary/5' : 'border-transparent hover:bg-muted/40',
        disabled && 'pointer-events-none opacity-60'
      )}
    >
      <Checkbox
        checked={selected}
        disabled={disabled}
        className="mt-0.5"
        aria-label={`选择 ${label}`}
        onCheckedChange={(checked) => {
          onSelectChange(candidate.id, checked === true)
        }}
      />
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-medium">{label}</div>
        {candidate.name ? (
          <div className="truncate text-xs text-muted-foreground">{candidate.email}</div>
        ) : null}
      </div>
    </label>
  )
}
