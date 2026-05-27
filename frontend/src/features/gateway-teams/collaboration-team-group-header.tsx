/**
 * 协作团队分组标题行（凭据/模型分组列表共用）。
 */

import type React from 'react'

import type { GatewayTeam } from '@/api/gateway/teams'
import { Badge } from '@/components/ui/badge'
import {
  gatewayTeamDisplayLabel,
  gatewayTeamRoleSubtitle,
} from '@/features/gateway-teams/gateway-team-display'
import { Users } from '@/lib/lucide-icons'

export interface CollaborationTeamGroupHeaderProps {
  team: GatewayTeam
  isPlatformAdmin: boolean
  viewerUserId?: string | null
  actions?: React.ReactNode
}

export function CollaborationTeamGroupHeader({
  team,
  isPlatformAdmin,
  viewerUserId,
  actions,
}: CollaborationTeamGroupHeaderProps): React.JSX.Element {
  const label = gatewayTeamDisplayLabel(team, { viewerUserId })
  const roleSubtitle = gatewayTeamRoleSubtitle(team, isPlatformAdmin)

  return (
    <div className="flex flex-wrap items-center gap-2 border-b bg-muted/20 px-4 py-2.5">
      <Users className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <p className="truncate font-medium">{label}</p>
          <Badge variant="outline" className="font-normal">
            {roleSubtitle}
          </Badge>
        </div>
        <p className="truncate font-mono text-[11px] text-muted-foreground">{team.slug}</p>
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </div>
  )
}
