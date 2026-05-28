import { useMemo } from 'react'
import type React from 'react'

import type { GatewayTeam } from '@/api/gateway/teams'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  gatewayTeamDisplayLabel,
  gatewayTeamRoleSubtitle,
} from '@/features/gateway-teams/gateway-team-display'
import { useGatewayPermission } from '@/hooks/use-gateway-permission'
import { ChevronsUpDown } from '@/lib/lucide-icons'
import { cn } from '@/lib/utils'
import { useUserStore } from '@/stores/user'

export interface GatewayTeamComboboxProps {
  value: string
  onChange: (teamId: string) => void
  teams: readonly GatewayTeam[]
  disabled?: boolean
  placeholder?: string
  className?: string
  popoverContentClassName?: string
  id?: string
  /** 选项与触发器主文案；默认 gatewayTeamDisplayLabel */
  labelForTeam?: (team: GatewayTeam) => string
}

export function GatewayTeamCombobox({
  value,
  onChange,
  teams,
  disabled = false,
  placeholder = '选择团队',
  className,
  popoverContentClassName,
  id,
  labelForTeam,
}: Readonly<GatewayTeamComboboxProps>): React.JSX.Element {
  const { isPlatformAdmin } = useGatewayPermission()
  const viewerUserId = useUserStore((s) => s.currentUser?.id ?? null)

  const resolveLabel = useMemo(() => {
    if (labelForTeam) return labelForTeam
    return (team: GatewayTeam) => gatewayTeamDisplayLabel(team, { viewerUserId })
  }, [labelForTeam, viewerUserId])

  const selectedTeam = useMemo(
    () => teams.find((team) => team.id === value) ?? null,
    [teams, value]
  )
  const triggerLabel = selectedTeam ? resolveLabel(selectedTeam) : placeholder

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          id={id}
          type="button"
          variant="outline"
          role="combobox"
          disabled={disabled || teams.length === 0}
          className={cn('w-full justify-between font-normal', className)}
        >
          <span className="truncate">{triggerLabel}</span>
          <ChevronsUpDown className="h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className={cn('min-w-[14rem]', popoverContentClassName)}>
        <DropdownMenuLabel className="text-xs font-normal text-muted-foreground">
          切换团队
        </DropdownMenuLabel>
        <DropdownMenuRadioGroup
          value={value}
          onValueChange={(nextTeamId) => {
            if (nextTeamId.length > 0) onChange(nextTeamId)
          }}
        >
          {teams.map((team) => (
            <DropdownMenuRadioItem key={team.id} value={team.id} className="gap-2">
              <span className="min-w-0 flex-1 truncate">{resolveLabel(team)}</span>
              <span className="shrink-0 text-[10px] uppercase text-muted-foreground">
                {gatewayTeamRoleSubtitle(team, isPlatformAdmin)}
              </span>
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
