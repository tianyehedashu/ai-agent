import type React from 'react'

import type { GatewayTeam } from '@/api/gateway/teams'
import { CommandItem } from '@/components/ui/command'
import {
  gatewayTeamCommandItemValue,
  gatewayTeamDisplayLabel,
  gatewayTeamRoleSubtitle,
} from '@/features/gateway-teams/gateway-team-display'
import { Check } from '@/lib/lucide-icons'
import { cn } from '@/lib/utils'

export interface GatewayTeamCommandItemsProps {
  teams: readonly GatewayTeam[]
  selectedTeamId?: string | null
  onSelectTeam: (teamId: string) => void
  isPlatformAdmin?: boolean
  viewerUserId?: string | null
}

export function GatewayTeamCommandItems({
  teams,
  selectedTeamId,
  onSelectTeam,
  isPlatformAdmin = false,
  viewerUserId = null,
}: Readonly<GatewayTeamCommandItemsProps>): React.JSX.Element {
  return (
    <>
      {teams.map((team) => (
        <CommandItem
          key={team.id}
          value={gatewayTeamCommandItemValue(team)}
          onSelect={() => {
            onSelectTeam(team.id)
          }}
        >
          <Check
            className={cn('mr-2 h-4 w-4', selectedTeamId === team.id ? 'opacity-100' : 'opacity-0')}
          />
          <div className="flex min-w-0 flex-1 items-center justify-between gap-2">
            <span className="truncate">{gatewayTeamDisplayLabel(team, { viewerUserId })}</span>
            <span className="text-[10px] uppercase text-muted-foreground">
              {gatewayTeamRoleSubtitle(team, isPlatformAdmin)}
            </span>
          </div>
        </CommandItem>
      ))}
    </>
  )
}
