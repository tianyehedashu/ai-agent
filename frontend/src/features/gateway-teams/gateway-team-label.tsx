/**
 * 团队 ID → 可读标签（Badge 或纯文本）
 */

import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

import { resolveTeamLabelFromMap } from './gateway-team-resolve-label'
import { useGatewayMemberTeamNameMap } from './use-gateway-teams'

export interface GatewayTeamLabelProps {
  teamId: string
  variant?: 'badge' | 'text'
  className?: string
}

export function GatewayTeamLabel({
  teamId,
  variant = 'badge',
  className,
}: Readonly<GatewayTeamLabelProps>): React.JSX.Element {
  const teamNameById = useGatewayMemberTeamNameMap()
  const label = resolveTeamLabelFromMap(teamNameById, teamId)

  if (variant === 'text') {
    return (
      <span className={cn('font-medium text-foreground', className)} title={teamId}>
        {label}
      </span>
    )
  }

  return (
    <Badge
      variant="secondary"
      className={cn('max-w-[12rem] truncate font-normal', className)}
      title={teamId}
    >
      {label}
    </Badge>
  )
}
